"""Stage an input-reviewed composition rebase without copying a Unity snapshot."""
from common import *
import re
import shutil


def private_path(value):
    path = (ROOT/value).resolve()
    if WORK.resolve() not in path.parents:
        raise RuntimeError('Composition migration paths must remain ignored under work/')
    return path


def stage_missing_sources():
    """Import current-source dependencies used only by the composed configuration."""
    from whole_catalog import copy_catalog_asset,repair_support_source
    from scene_closure import REFERENCE
    from build import preflight
    preflight()
    project=WORK/'lab-project'
    export=ROOT/read(WORK/'config/reconstruction.json')['projects'][0]
    catalog=ROOT/read(WORK/'experiments/whole-catalog/latest.json')['path']
    index=read(catalog/'source-guid-index.json');guids={path:guid for guid,path in index.items()}
    selection=read(WORK/'config/composition-migration.json')
    evidence=private_path(selection['evidence'])/('dependency-stage-'+now());evidence.mkdir()
    remaps=read(WORK/'config/hud-ui-remaps.json')
    if selection['input_id']!=read(project/'.port-input.json')['input_id'] or remaps['input_id']!=selection['input_id']:
        raise RuntimeError('Composition dependency generation mismatch')
    owners={}
    for meta in (project/'Assets').rglob('*.meta'):
        match=re.search(r'^guid:\s*([a-f0-9]{32})',meta.read_text(errors='replace'),re.M)
        if match:
            if match[1] in owners:raise RuntimeError('Duplicate imported GUID owner')
            owners[match[1]]=str(Path(str(meta)[:-5]).relative_to(project))
    def paths(value):
        if isinstance(value,str):return {value} if value.startswith('Assets/') else set()
        if isinstance(value,dict):return paths(list(value.values()))
        if isinstance(value,(list,tuple)):
            return set().union(*(paths(item) for item in value)) if value else set()
        return set()
    required=paths(read(WORK/'scene-probe-build.json'))|paths(read(project/'Assets/LabLoadingScene/Resources/MovementBatchProbe.json'))
    missing=sorted(path for path in required if not (project/path).is_file())
    if any(not path.startswith('Assets/WholeGame/') for path in missing):
        raise RuntimeError('Missing authored composition asset; refuse original-source substitution')
    pending=['Assets/'+path.removeprefix('Assets/WholeGame/') for path in missing]
    mapped={};copied=[];unresolved=[]
    while pending:
        relative=pending.pop()
        if relative in mapped:continue
        source=export/relative;guid=guids.get(relative)
        if not guid or not source.is_file():raise RuntimeError('Composed current source missing: '+relative)
        if guid in owners:
            mapped[relative]=owners[guid];continue
        if source.suffix=='.dll':raise RuntimeError('Composed dependency needs an unprovided runtime assembly: '+relative)
        target_relative='Assets/WholeGame/'+relative.removeprefix('Assets/');target=project/target_relative
        copy_catalog_asset(source,target);copy_catalog_asset(Path(str(source)+'.meta'),Path(str(target)+'.meta'))
        mapped[relative]=target_relative;owners[guid]=target_relative
        with source.open('rb') as stream:yaml=stream.read(5)==b'%YAML'
        if yaml:
            original=source.read_text();text=original
            for row in remaps['rows']:text=text.replace(row['from'],row['to'])
            if text!=original:target.write_text(text)
            for _,dependency,_ in REFERENCE.findall(original):
                if not dependency or dependency.startswith('0000000000000000'):continue
                if dependency in index:pending.append(index[dependency])
                else:unresolved.append(dict(source=relative,guid=dependency))
        copied.append(dict(source=relative,source_sha256=sha(source),target=target_relative,sha256=sha(target)))
    repair_support_source(export,mapped,project,evidence)
    from integrated_objective import sanitize_optional_content
    sanitize_optional_content(project/'Assets/LabLoadingScene',evidence,project/'Assets/WholeGame')
    if any(not (project/path).is_file() for path in required):raise RuntimeError('Composed paths remain missing after current dependency import')
    write(evidence/'receipt.json',dict(input_id=selection['input_id'],missing_roots=missing,copied=copied,unresolved=unresolved))
    print(json.dumps(dict(missing_roots=len(missing),copied=len(copied),unresolved=len(unresolved),evidence=str(evidence.relative_to(ROOT)))))


def stage():
    from build import preflight
    preflight()
    selection = read(WORK/'config/composition-migration.json')
    evidence = private_path(selection['evidence'])
    previous = private_path(selection['previous_project'])
    export = ROOT/read(WORK/'config/reconstruction.json')['projects'][0]
    project = WORK/'lab-project'
    accepted = read(WORK/'config/accepted-input.json')['input_id']
    if selection['input_id'] != accepted or read(project/'.port-input.json')['input_id'] != accepted:
        raise RuntimeError('Composition rebase belongs to a different accepted input')
    if previous.resolve() == project.resolve():
        raise RuntimeError('Previous composition must remain a separate rollback')
    plan = read(evidence/'semantic-preview-result.json')
    if plan['conflicts']:
        raise RuntimeError('Unresolved serialized rebase; refuse partial composition staging')
    catalog = ROOT/read(WORK/'experiments/whole-catalog/latest.json')['path']
    index = read(catalog/'source-guid-index.json')
    guids = {path:guid for guid,path in index.items()}
    owners = {}
    for meta in (project/'Assets').rglob('*.meta'):
        match = re.search(r'^guid:\s*([a-f0-9]{32})',meta.read_text(errors='replace'),re.M)
        if match:
            if match[1] in owners:
                raise RuntimeError('Duplicate current GUID owner')
            owners[match[1]] = str(Path(str(meta)[:-5]).relative_to(project))
    remaps = read(WORK/'config/hud-ui-remaps.json')
    if remaps['input_id'] != accepted:
        raise RuntimeError('UI bindings belong to a different input')
    analysis = read(evidence/'asset-analysis.json')['rows']
    path_overrides = selection.get('source_path_overrides', {})
    guidmap = read(evidence/'rebase-analysis.json')['guidmap']
    removed = selection.get('removed_state_configs', {})
    if removed:
        proof = read(evidence/'removed-state-types.json')
        present = {row['name'] for row in proof['contract']['types']}
        if proof['contract']['sha256'] != sha(game()/'Risk of Rain 2_Data/Managed/RoR2.dll'):
            raise RuntimeError('Removed state proof belongs to another input')
        for path,type_name in removed.items():
            if proof['paths'].get(path) != type_name or type_name in present:
                raise RuntimeError('State removal lacks exact current TypeDef absence evidence')
    removed_bindings = []
    assetmap = {}
    absent = []
    generated = []
    for row in analysis:
        old_path = row['old']
        if row.get('old_source'):
            source = path_overrides.get(row['old_source'],row['old_source'])
            guid = guids.get(source)
            if not guid:
                absent.append(old_path)
                continue
            guidmap[row['guid']] = guid
            assetmap[old_path.casefold()] = owners.get(guid,'Assets/WholeGame/'+source.removeprefix('Assets/'))
        else:
            if not old_path.startswith('Assets/LabLoadingScene/') or any(part.startswith(('Retired','J371Archived','J379Archived')) for part in Path(old_path).parts):
                continue
            if row['kind'] == '.cs' or '/Editor/' in old_path or row['kind'] == '.xml' or Path(old_path).name == 'WholeCatalogBootstrap.json':
                continue
            target = owners.get(row['guid'],old_path)
            assetmap[old_path.casefold()] = target
            generated.append(dict(row,target=target))
    missing_runtime = []
    def retarget(value):
        if isinstance(value,list):
            result = []
            for item in value:
                if isinstance(item,str) and item in removed:
                    removed_bindings.append(dict(asset=item,type=removed[item]))
                else:
                    result.append(retarget(item))
            return result
        if isinstance(value,dict):
            return {k:retarget(v) for k,v in value.items()}
        if isinstance(value,str) and value.casefold().startswith('assets/'):
            mapped = assetmap.get(value.casefold())
            if mapped is None:
                missing_runtime.append(value)
                return value
            return mapped
        return value
    config_path = previous/'Assets/LabLoadingScene/Resources/MovementBatchProbe.json'
    configuration = retarget(read(config_path))
    chest_source = export/'Assets/RoR2/Base/Interactables/Chest1/Chest1.prefab'
    costs = re.findall(r'^  cost: (\d+)$',chest_source.read_text(),re.M)
    if configuration.get('originalMoneyCost'):
        if costs != ['25']:
            raise RuntimeError('Updated original Chest1 cost requires contract review')
        configuration['moneySourceSha256'] = sha(chest_source)
    recipe = read(WORK/'scene-probe-build.json')
    # Removed original inputs are not incompatibility quarantines or fallbacks.
    recipe['prefabAssets'] = [path for path in recipe['prefabAssets'] if path.casefold() in assetmap]
    recipe = retarget(recipe)
    if missing_runtime:
        write(evidence/'missing-runtime-bindings.json',sorted(set(missing_runtime)))
        raise RuntimeError('Composition still references removed or unowned assets; inspect missing-runtime-bindings.json')
    def normalize(text):
        text = re.sub(r'(?<=guid: )[a-f0-9]{32}',lambda m:guidmap.get(m[0],m[0]),text)
        for row in remaps['rows']:
            text = text.replace(row['from'],row['to'])
        return text
    # Verify the entire patch plan before the first project write.
    for row in plan['rows']:
        output = evidence/'preview'/row['target']
        if sha(output) != row['output_sha'] or sha(export/row['source']) != row['current_source_sha256'] or sha(previous/row['old']) != row['previous_adapted_sha256']:
            raise RuntimeError('Serialized rebase provenance drift: '+row['source'])
        target = project/row['target']
        if target.exists() and sha(target) not in {row['target_before_sha256'],row['output_sha']}:
            raise RuntimeError('Current project changed after the rebase: '+row['target'])
    staged = []
    for row in generated:
        source = previous/row['old']
        target = project/row['target']
        target.parent.mkdir(parents=True,exist_ok=True)
        data = source.read_bytes()
        target.write_bytes(normalize(data.decode()).encode() if data.startswith(b'%YAML') else data)
        shutil.copy2(Path(str(source)+'.meta'),Path(str(target)+'.meta'))
        staged.append(row['target'])
    for row in plan['rows']:
        target = project/row['target']
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(evidence/'preview'/row['target'],target)
        meta = Path(str(target)+'.meta')
        if not meta.exists():
            text = Path(str(export/row['source'])+'.meta').read_text()
            meta.write_text(re.sub(r'(?<=guid: )[a-f0-9]{32}',guids[row['source']],text,count=1))
        staged.append(row['target'])
    # Native source outputs replace the old recovered resources by name. Their
    # current binary/tool receipts remain local; this does not assert PC parity.
    native_names = set()
    for directory in selection['shader_sources']:
        source = private_path(directory)
        receipt = read(source.parent/'receipt.json')
        if not receipt['success']:
            raise RuntimeError('Current native binding generation failed')
        for file in source.iterdir():
            if file.is_file():
                if sha(file) != receipt['source_sha256_by_file'][file.name]:
                    raise RuntimeError('Native generated source drift')
                target = project/'Assets/LabLoadingScene/Resources'/file.name
                shutil.copy2(file,target)
                native_names.add(file.name)
                staged.append(str(target.relative_to(project)))
    for path in (project/'Assets/LabLoadingScene/Resources').glob('AndroidNative*.shader'):
        if path.name not in native_names:
            path.unlink()
            Path(str(path)+'.meta').unlink(missing_ok=True)
    global_textures=[]
    for row in selection.get('native_global_textures',[]):
        source=export/row['source'];target=project/'Assets/LabLoadingScene/Resources'/row['resource']
        if source.suffix!='.png' or target.parent!=project/'Assets/LabLoadingScene/Resources' or sha(source)!=row['sha256']:
            raise RuntimeError('Current original global texture identity changed')
        def importer(path):
            return re.sub(r'(?m)^(?:guid|timeCreated): .*\n','',Path(str(path)+'.meta').read_text())
        if importer(source)!=importer(target):raise RuntimeError('Native global texture importer requires review')
        before=sha(target);shutil.copy2(source,target)
        global_textures.append(dict(row,before_sha256=before,after_sha256=sha(target)))
    from whole_catalog import copy_catalog_asset
    copy_catalog_asset(ROOT/'tools/unity/AndroidNativeDeferredPresentation.cs',project/'Assets/LabLoadingScene/AndroidNativeDeferredPresentation.cs')
    configuration['attempt'] = evidence.name
    configuration['pauseBeforeMoon'] = True
    write(project/'Assets/LabLoadingScene/Resources/MovementBatchProbe.json',configuration)
    write(WORK/'scene-probe-build.json',recipe)
    # Reapply the accepted shared unavailable-presentation boundary as part of
    # importing the composed-only current dependencies.
    stage_missing_sources()
    # A fresh attempt is necessary for existing build/run attribution. It is a
    # small receipt, never another project snapshot or inherited assembly proof.
    generation = read(project/'.port-input.json')
    old_attempt = ROOT/read(WORK/'experiments/scene-runtime/current.json')['path']
    mapping = read(old_attempt/'nova-input-mapping.json')
    if sha(ROOT/mapping['observation']) != mapping['observation_sha256']:
        raise RuntimeError('Accepted physical mapping evidence changed')
    mapping['attempt'] = evidence.name
    write(evidence/'nova-input-mapping.json',mapping)
    probe = 'body-state-spawn-state-auto-nova-spine-bringup'
    write(evidence/'attempt.json',dict(attempt=evidence.name,input_id=accepted,stage=str(project/'Assets/LabLoadingScene'),
          original_assemblies=generation['original_assemblies'],transformed_assemblies=generation['transformed_assemblies'],
          movement_batch=True,playable_spine=True,integrated_world=True,teleporter_loop=True,
          batch_ids=[probe],batch_seconds={probe:900},batch_stop_when_complete=[probe],
          status='Updated composed generation staged; Android acceptance pending'))
    write(WORK/'experiments/scene-runtime/current.json',dict(path=str(evidence.relative_to(ROOT))))
    write(evidence/'staging-result.json',dict(input_id=accepted,staged=len(set(staged)),source_adaptations=len(plan['rows']),
          original_input_removals=absent,retargeted_assets=len(assetmap),native_sources=len(native_names),
          removed_state_bindings=removed_bindings,
          native_global_textures=global_textures,
          scope='Current ignored composition generation only; no Android or complete gameplay acceptance'))
    print(json.dumps(read(evidence/'staging-result.json')))
