"""Stage an input-reviewed composition rebase without copying a Unity snapshot."""

from common import *
import hashlib
import re
import shutil


def private_path(value):
    path = (ROOT / value).resolve()
    if WORK.resolve() not in path.parents:
        raise RuntimeError("Composition migration paths must remain ignored under work/")
    return path


def assembly_paths(project, generation):
    result = {}
    for name, original in generation["original_assemblies"].items():
        matches = list((project / "Assets").rglob(name))
        expected = generation.get("transformed_assemblies", {}).get(name, original)
        if len(matches) != 1 or sha(matches[0]) != expected:
            raise RuntimeError("Current runtime assembly placement/identity is ambiguous: " + name)
        result[name] = str(matches[0].relative_to(project))
    return result


def restore_script_orders(project, source):
    """Retain shipped nonzero MonoScript orders on the corresponding runtime DLLs."""
    import UnityPy

    generation = read(project / ".port-input.json")
    paths = assembly_paths(project, generation)
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
        text = meta.read_text()
        match = re.search(r"^  executionOrder:(?: \{\})?\n(?:    .*\n)*", text, re.M)
        if not match:
            raise RuntimeError("Runtime plugin execution-order metadata missing: " + assembly)
        prior = {}
        for line in match[0].splitlines()[1:]:
            name, value = line.strip().rsplit(": ", 1)
            prior[name] = int(value)
        merged = dict(prior, **orders)
        block = "  executionOrder:\n" + "".join("    " + name + ": " + str(value) + "\n" for name, value in sorted(merged.items()))
        plan.append((meta, text[: match.start()] + block + text[match.end() :], dict(assembly=assembly, orders=orders, before_sha256=sha(meta))))
    # Validate all owners before writing any importer.
    for meta, text, row in plan:
        meta.write_text(text)
        row["after_sha256"] = sha(meta)
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


def refresh_scene_contracts(project, export, configuration, recipe):
    observations = []
    stages = {row["scene"]: row for row in configuration["integratedStages"] if not row.get("moonMission")}
    for path in [recipe["stageScene"]] + [row["scene"] for row in configuration["integratedStages"] if not row.get("moonMission")]:
        staged = project / path
        source = export / ("Assets/" + path.removeprefix("Assets/WholeGame/"))
        before = sha(staged)
        text, counts, removed = scene_contract(source.read_text(), staged.read_text())
        if text != staged.read_text():
            staged.write_text(text)
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
            dict(scene=path, source_sha256=sha(source), before_sha256=before, after_sha256=sha(staged), removed_nonzone_network_components=removed, **counts)
        )
    return observations


def stage_missing_sources():
    """Import current-source dependencies used only by the composed configuration."""
    from whole_catalog import copy_catalog_asset, repair_support_source
    from scene_closure import REFERENCE
    from build import preflight

    preflight()
    project = WORK / "lab-project"
    export = ROOT / read(WORK / "config/reconstruction.json")["projects"][0]
    catalog = ROOT / read(WORK / "experiments/whole-catalog/latest.json")["path"]
    index = read(catalog / "source-guid-index.json")
    guids = {path: guid for guid, path in index.items()}
    selection = read(WORK / "config/composition-migration.json")
    evidence = private_path(selection["evidence"]) / ("dependency-stage-" + now())
    evidence.mkdir()
    remaps = read(RECIPE / "hud-ui-remaps.json")
    if selection["input_id"] != read(project / ".port-input.json")["input_id"] or remaps["input_id"] != selection["input_id"]:
        raise RuntimeError("Composition dependency generation mismatch")
    owners = {}
    for meta in (project / "Assets").rglob("*.meta"):
        match = re.search(r"^guid:\s*([a-f0-9]{32})", meta.read_text(errors="replace"), re.M)
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

    required = paths(read(WORK / "scene-probe-build.json")) | paths(read(project / "Assets/LabLoadingScene/Resources/MovementBatchProbe.json"))
    missing = sorted(path for path in required if not (project / path).is_file())
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
        if guid in owners:
            mapped[relative] = owners[guid]
            continue
        if source.suffix == ".dll":
            raise RuntimeError("Composed dependency needs an unprovided runtime assembly: " + relative)
        target_relative = "Assets/WholeGame/" + relative.removeprefix("Assets/")
        target = project / target_relative
        copy_catalog_asset(source, target)
        copy_catalog_asset(Path(str(source) + ".meta"), Path(str(target) + ".meta"))
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
                target.write_text(text)
            for _, dependency, _ in REFERENCE.findall(original):
                if not dependency or dependency.startswith("0000000000000000"):
                    continue
                if dependency in index:
                    pending.append(index[dependency])
                else:
                    unresolved.append(dict(source=relative, guid=dependency))
        copied.append(dict(source=relative, source_sha256=sha(source), target=target_relative, sha256=sha(target)))
    repair_support_source(export, mapped, project, evidence)
    from integrated_objective import sanitize_optional_content

    sanitize_optional_content(project / "Assets/LabLoadingScene", evidence, project / "Assets/WholeGame")
    if any(not (project / path).is_file() for path in required):
        raise RuntimeError("Composed paths remain missing after current dependency import")
    write(evidence / "receipt.json", dict(input_id=selection["input_id"], missing_roots=missing, copied=copied, unresolved=unresolved))
    print(json.dumps(dict(missing_roots=len(missing), copied=len(copied), unresolved=len(unresolved), evidence=str(evidence.relative_to(ROOT)))))


def prepare_asset_transforms(plan, transforms, export, previous, evidence, project, guids):
    """Validate all stage rows before writes; recipe rows need no historical asset bytes."""
    from asset_transforms import generate_asset

    transformed = {}
    for row in plan["rows"]:
        if sha(export / row["source"]) != row["current_source_sha256"]:
            raise RuntimeError("Serialized rebase provenance drift: " + row["source"])
        if row["target"] not in transforms:
            output = evidence / "preview" / row["target"]
            if sha(output) != row["output_sha"] or sha(previous / row["old"]) != row["previous_adapted_sha256"]:
                raise RuntimeError("Serialized rebase provenance drift: " + row["source"])
        target = project / row["target"]
        if target.exists() and sha(target) not in {row["target_before_sha256"], row["output_sha"]}:
            raise RuntimeError("Current project changed after the rebase: " + row["target"])
        if row["target"] in transforms:
            asset = transforms[row["target"]]
            if asset["source"] != row["source"] or asset["source_sha256"] != row["current_source_sha256"]:
                raise RuntimeError("Asset transform disagrees with composition provenance: " + row["target"])
            data, meta_data = generate_asset(export, asset, guids[row["source"]])
            if hashlib.sha256(data).hexdigest() != row["output_sha"]:
                raise RuntimeError("Asset transform differs from composition oracle: " + row["target"])
            meta = Path(str(target) + ".meta")
            if meta.exists() and meta.read_bytes() != meta_data:
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


def stage_addition(row, authored, previous, project, guidmap, remaps):
    target = project / row["target"]
    target.parent.mkdir(parents=True, exist_ok=True)
    if row["old"] in authored:
        data, meta_data = authored[row["old"]]
        target.write_bytes(data)
        Path(str(target) + ".meta").write_bytes(meta_data)
    else:
        source = previous / row["old"]
        target.write_bytes(normalize_addition(source.read_bytes(), guidmap, remaps))
        shutil.copy2(Path(str(source) + ".meta"), Path(str(target) + ".meta"))


def stage():
    from build import preflight

    preflight()
    selection = read(WORK / "config/composition-migration.json")
    evidence = private_path(selection["evidence"])
    previous = private_path(selection["previous_project"])
    export = ROOT / read(WORK / "config/reconstruction.json")["projects"][0]
    project = WORK / "lab-project"
    accepted = read(WORK / "config/accepted-input.json")["input_id"]
    if selection["input_id"] != accepted or read(project / ".port-input.json")["input_id"] != accepted:
        raise RuntimeError("Composition rebase belongs to a different accepted input")
    if previous.resolve() == project.resolve():
        raise RuntimeError("Previous composition must remain a separate rollback")
    plan = read(evidence / "semantic-preview-result.json")
    if plan["conflicts"]:
        raise RuntimeError("Unresolved serialized rebase; refuse partial composition staging")
    catalog = ROOT / read(WORK / "experiments/whole-catalog/latest.json")["path"]
    index = read(catalog / "source-guid-index.json")
    guids = {path: guid for guid, path in index.items()}
    owners = {}
    for meta in (project / "Assets").rglob("*.meta"):
        match = re.search(r"^guid:\s*([a-f0-9]{32})", meta.read_text(errors="replace"), re.M)
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
        if proof["contract"]["sha256"] != sha(game() / "Risk of Rain 2_Data/Managed/RoR2.dll"):
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
    recipe = read(WORK / "scene-probe-build.json")
    # Removed original inputs are not incompatibility quarantines or fallbacks.
    recipe["prefabAssets"] = [path for path in recipe["prefabAssets"] if path.casefold() in assetmap]
    recipe = retarget(recipe)
    if missing_runtime:
        write(evidence / "missing-runtime-bindings.json", sorted(set(missing_runtime)))
        raise RuntimeError("Composition still references removed or unowned assets; inspect missing-runtime-bindings.json")

    # Verify the entire patch plan before the first project write.
    from asset_transforms import load_recipe, prepare_decks
    from authored_additions import prepare as prepare_authored_additions
    from shader_additions import prepare as prepare_shader_additions

    transforms = {asset["output"]: asset for asset in load_recipe(accepted)["assets"]}
    transformed = prepare_asset_transforms(plan, transforms, export, previous, evidence, project, guids)
    authored = prepare_authored_additions(generated)
    shaders = prepare_shader_additions(generated)
    if authored.keys() & shaders.keys():
        raise RuntimeError("Overlapping generated addition owners")
    authored.update(shaders)
    decks = prepare_decks(generated, export, accepted)
    if authored.keys() & decks.keys():
        raise RuntimeError("Overlapping generated addition owners")
    authored.update(decks)
    staged = []
    for row in generated:
        stage_addition(row, authored, previous, project, guidmap, remaps)
        staged.append(row["target"])
    for row in plan["rows"]:
        target = project / row["target"]
        target.parent.mkdir(parents=True, exist_ok=True)
        if row["target"] in transformed:
            data, meta_data = transformed[row["target"]]
            target.write_bytes(data)
            Path(str(target) + ".meta").write_bytes(meta_data)
            staged.append(row["target"])
            continue
        shutil.copy2(evidence / "preview" / row["target"], target)
        meta = Path(str(target) + ".meta")
        if not meta.exists():
            text = Path(str(export / row["source"]) + ".meta").read_text()
            meta.write_text(re.sub(r"(?<=guid: )[a-f0-9]{32}", guids[row["source"]], text, count=1))
        staged.append(row["target"])
    # Native source outputs replace the old recovered resources by name. Their
    # current binary/tool receipts remain local; this does not assert PC parity.
    native_names = set()
    for directory in selection["shader_sources"]:
        source = private_path(directory)
        receipt = read(source.parent / "receipt.json")
        if not receipt["success"]:
            raise RuntimeError("Current native binding generation failed")
        for file in source.iterdir():
            if file.is_file():
                if sha(file) != receipt["source_sha256_by_file"][file.name]:
                    raise RuntimeError("Native generated source drift")
                target = project / "Assets/LabLoadingScene/Resources" / file.name
                generated_pair = shaders.get(str(target.relative_to(project)))
                if generated_pair is not None:
                    if file.read_bytes() != generated_pair[0]:
                        raise RuntimeError("Native source differs from regenerated shader pair")
                else:
                    shutil.copy2(file, target)
                native_names.add(file.name)
                staged.append(str(target.relative_to(project)))
    for path in (project / "Assets/LabLoadingScene/Resources").glob("AndroidNative*.shader"):
        if path.name not in native_names:
            path.unlink()
            Path(str(path) + ".meta").unlink(missing_ok=True)
    global_textures = []
    for row in selection.get("native_global_textures", []):
        source = export / row["source"]
        target = project / "Assets/LabLoadingScene/Resources" / row["resource"]
        if source.suffix != ".png" or target.parent != project / "Assets/LabLoadingScene/Resources" or sha(source) != row["sha256"]:
            raise RuntimeError("Current original global texture identity changed")

        def importer(path):
            return re.sub(r"(?m)^(?:guid|timeCreated): .*\n", "", Path(str(path) + ".meta").read_text())

        if importer(source) != importer(target):
            raise RuntimeError("Native global texture importer requires review")
        before = sha(target)
        shutil.copy2(source, target)
        global_textures.append(dict(row, before_sha256=before, after_sha256=sha(target)))
    from whole_catalog import copy_catalog_asset

    copy_catalog_asset(
        ROOT / "tools/unity/runtime/shaders/AndroidNativeDeferredPresentation.cs", project / "Assets/LabLoadingScene/AndroidNativeDeferredPresentation.cs"
    )
    configuration["attempt"] = evidence.name
    configuration["pauseBeforeMoon"] = True
    write(project / "Assets/LabLoadingScene/Resources/MovementBatchProbe.json", configuration)
    write(WORK / "scene-probe-build.json", recipe)
    # Reapply the accepted shared unavailable-presentation boundary as part of
    # importing the composed-only current dependencies.
    stage_missing_sources()
    scene_contracts = refresh_scene_contracts(project, export, configuration, recipe)
    write(project / "Assets/LabLoadingScene/Resources/MovementBatchProbe.json", configuration)
    write(evidence / "current-scene-contracts.json", scene_contracts)
    # A fresh attempt is necessary for existing build/run attribution. It is a
    # small receipt, never another project snapshot or inherited assembly proof.
    generation = read(project / ".port-input.json")
    write(evidence / "current-original-script-orders.json", restore_script_orders(project, game() / "Risk of Rain 2_Data/globalgamemanagers.assets"))
    old_attempt = ROOT / read(WORK / "experiments/scene-runtime/current.json")["path"]
    mapping = read(old_attempt / "nova-input-mapping.json")
    if sha(ROOT / mapping["observation"]) != mapping["observation_sha256"]:
        raise RuntimeError("Accepted physical mapping evidence changed")
    mapping["attempt"] = evidence.name
    write(evidence / "nova-input-mapping.json", mapping)
    probe = "body-state-spawn-state-auto-nova-spine-bringup"
    write(
        evidence / "attempt.json",
        dict(
            attempt=evidence.name,
            input_id=accepted,
            stage=str(project / "Assets/LabLoadingScene"),
            original_assemblies=generation["original_assemblies"],
            transformed_assemblies=generation["transformed_assemblies"],
            assembly_paths=assembly_paths(project, generation),
            configuration_sha256=sha(project / "Assets/LabLoadingScene/Resources/MovementBatchProbe.json"),
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
    write(WORK / "experiments/scene-runtime/current.json", dict(path=str(evidence.relative_to(ROOT))))
    write(
        evidence / "staging-result.json",
        dict(
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
    print(json.dumps(read(evidence / "staging-result.json")))
