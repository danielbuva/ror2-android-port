"""Stage the five measured base-game scene variants without changing native stage selection."""
import gzip
import json
import re
import shutil
from pathlib import Path

from common import ROOT, WORK, now, read, sha, write

VARIANTS = {
    'blackbeach': '9672ae28cd6b03b2c7533f6084607595858708a148ee5e66114fc61f70c43a58',
    'blackbeach2': '39ec58020c56dac7275538d4f529383b0dc73615a28c03e2273e92c12467d93a',
    'golemplains2': 'f3dcbfa1cf86a3e1bc3d42642b199114ce403543a41f4c00ccf5410e30ad297f',
    'goolake': 'edbd7dfa00ab03ea1d1cfa723afea5f0985ccfc6820d5ff86da0c971d3011b6d',
    'rootjungle': '9208b430b51ff6feae9c687fc7e35c0bd103e5749fefff5759c8f2ca4237d1c3',
}


def include_runtime_graph_roots(config, recipe, project, accepted_files):
    """Keep each accepted stage graph in the bundle queried by transport."""
    accepted = {path.casefold(): (path, digest) for path, digest in accepted_files.items()}
    existing = {path.casefold() for path in recipe.get('prefabAssets', [])}
    added = []
    for stage in config['integratedStages']:
        if stage['name'] not in VARIANTS:
            continue
        for field in ('groundGraph', 'airGraph'):
            key = stage[field].casefold()
            if key not in accepted:
                raise RuntimeError('Variant graph is absent from accepted inputs: '+stage['name']+'/'+field)
            path, digest = accepted[key]
            if sha(project/path) != digest:
                raise RuntimeError('Accepted variant graph changed: '+stage['name']+'/'+field)
            if key not in existing:
                recipe.setdefault('prefabAssets', []).append(path)
                existing.add(key)
                added.append(path)
    return added


def stage():
    from build import preflight
    from composition_migration import scene_contract
    from nova_bridge import stage_first_stage_geometry
    from whole_catalog import original_stage_contexts

    preflight()
    project = WORK/'lab-project'
    input_id = read(WORK/'config/accepted-input.json')['input_id']
    if read(project/'.port-input.json')['input_id'] != input_id:
        raise RuntimeError('Stage project belongs to a different accepted game input')
    export = ROOT/read(WORK/'config/reconstruction.json')['projects'][0]
    config_path = project/'Assets/LabLoadingScene/Resources/MovementBatchProbe.json'
    context_path = project/'Assets/LabLoadingScene/Resources/WholeStageContexts.json'
    editor_path = project/'Assets/Editor/LabBuild.cs'
    recipe_path = WORK/'scene-probe-build.json'
    config = read(config_path)
    recipe = read(recipe_path)
    accepted_files = read(WORK/'whole-catalog-code-base.json')['files']
    accepted_payload = {path.lower():digest for path,digest in accepted_files.items()}
    names = [row['name'] for row in config['integratedStages']]
    pending = list(VARIANTS)
    if all(name in names for name in pending):
        if all(sha(project/'Assets/WholeGame/RoR2/Base/Scenes'/name/(name+'.unity')) == digest
               for name,digest in VARIANTS.items()):
            for row in config['integratedStages']:
                if row['name'] in VARIANTS:
                    row['previewNames'] = sorted(row['previewNames'])
            added = include_runtime_graph_roots(config,recipe,project,accepted_files)
            write(config_path,config)
            if added:write(recipe_path,recipe)
            return {'success':True, 'already_staged':True, 'stages':pending,'runtime_graph_roots_added':added}
        raise RuntimeError('Previously staged scene variant changed; review before regenerating')
    if any(name in names for name in pending):
        raise RuntimeError('Partial stage-variant configuration requires review')
    if len({row['name'] for row in config['stageCombatDecks']}) != len(config['stageCombatDecks']):
        raise RuntimeError('Duplicate existing stage-combat contract')
    if any(name in {row['name'] for row in config['stageCombatDecks']} for name in pending):
        raise RuntimeError('Stage-combat variant was staged without its scene')
    temporary = project/'Assets/LabLoadingScene/StageGeometry'
    if temporary.exists():
        raise RuntimeError('Temporary StageGeometry is not empty; refuse to overwrite unrelated work')

    out = WORK/'experiments/stage-variants'/now()
    out.mkdir(parents=True)
    originals = out/'previous-scenes'
    originals.mkdir()
    candidates = {}
    source_receipts = []
    recipe_before = recipe_path.read_bytes()
    try:
        for name,digest in VARIANTS.items():
            target = project/'Assets/WholeGame/RoR2/Base/Scenes'/name/(name+'.unity')
            source = export/'Assets/RoR2/Base/Scenes'/name/(name+'.unity')
            if not target.is_file() or not source.is_file():
                raise RuntimeError('Accepted scene source is missing: '+name)
            if sha(target) == digest:
                raise RuntimeError('Converted scene exists outside the stage-variant configuration: '+name)
            with gzip.open(originals/(name+'.unity.gz'),'wb',compresslevel=6) as archive:
                archive.write(target.read_bytes())
            spec = stage_first_stage_geometry(project/'Assets/LabLoadingScene',out,
                    original_name=True,scene_name=name,map_zones=True,presentation=True,billboards=True)
            generated = temporary/(name+'.unity')
            if sha(generated) != digest:
                raise RuntimeError('Recovered scene variant differs from the measured source projection: '+name)
            checked,counts,removed = scene_contract(source.read_text(),generated.read_text())
            if checked != generated.read_text() or removed:
                raise RuntimeError('Recovered scene has an unexpected callback or network owner: '+name)
            if sorted(spec['previewNames']) != counts['previewNames'] or any(spec[key] != counts[key] for key in ('previewCallbacks','mapZoneCount','mapZoneActiveNames','mapZoneNetworkObjects','emptyMeshPaths','emptyColliderPaths')):
                raise RuntimeError('Scene contract report differs from source projection: '+name)
            spec['previewNames'] = counts['previewNames']
            prefix = 'assets/labloadingscene/stagegeometry/assets/'
            for kind in ('groundGraph','airGraph'):
                if not spec[kind].startswith(prefix):
                    raise RuntimeError('Unexpected graph import location: '+name)
                imported = project/('Assets/WholeGame/'+spec[kind][len(prefix):])
                staged = project/spec[kind]
                if not imported.is_file() or not staged.is_file():
                    raise RuntimeError('Original stage graph is missing: '+name+'/'+kind)
                # The imported graph is the accepted compact conversion, so its
                # bytes differ from the raw exported graph while the GUID agrees.
                relative = str(imported.relative_to(project)).lower()
                if sha(imported) != accepted_payload.get(relative):
                    raise RuntimeError('Accepted converted graph changed: '+name+'/'+kind)
                def guid(asset):
                    match = re.search(r'^guid: ([a-f0-9]{32})$',Path(str(asset)+'.meta').read_text(),re.M)
                    if not match:raise RuntimeError('Stage graph metadata has no GUID: '+name+'/'+kind)
                    return match[1]
                if guid(imported) != guid(staged):
                    raise RuntimeError('Original graph GUID differs from imported stage graph: '+name+'/'+kind)
                spec[kind] = 'assets/wholegame/'+spec[kind][len(prefix):]
            spec['scene'] = str(target.relative_to(project)).lower()
            candidates[name] = (generated.read_bytes(),spec,target)
            source_receipts.append({'name':name,'source_sha256':sha(source),
                                    'previous_sha256':sha(target),'generated_sha256':digest,
                                    'preview_callbacks':counts['previewCallbacks'],
                                    'map_zones':counts['mapZoneCount']})

        catalog = ROOT/read(WORK/'experiments/whole-catalog/latest.json')['path']
        attempt = ROOT/read(catalog/'integration-latest.json')['path']
        manifest = read(attempt/'manifest.json')
        pool_keys = {}
        for row in manifest['locations']:
            if not row['type'].startswith('RoR2.DccsPool,'):
                continue
            meta = (project/(row['path']+'.meta')).read_text()
            guid = re.search(r'^guid: ([a-f0-9]{32})$',meta,re.M)[1]
            if guid in pool_keys and pool_keys[guid] != row['primaryKey']:
                raise RuntimeError('Ambiguous original stage pool identity')
            pool_keys[guid] = row['primaryKey']
        next_names = names + pending
        contexts = original_stage_contexts(export,[row['name'] for row in config['stageCombatDecks']]+pending,input_id,pool_keys)
        for name in pending:
            config['integratedStages'].append(candidates[name][1])
            config['stageCombatDecks'].append({'name':name,'asset':'','cards':0,'categories':0,'excluded':0})
            scene = str(candidates[name][2].relative_to(project))
            if scene not in recipe['nextStageScenes']:
                recipe['nextStageScenes'].append(scene)
        added_graphs = include_runtime_graph_roots(config,recipe,project,accepted_files)
        write(out/'preview.json',{'input_id':input_id,'scenes':source_receipts,
            'stage_names':next_names,
            'prior_art':'Pinned R2API.Director stage/SceneCatalog seams informed the validation boundary; shipped scene and pool records are authoritative. Native stage selection is unchanged.'})
        backups = {path:path.read_bytes() for path in (config_path,context_path,editor_path,recipe_path)}
        backups.update({entry[2]:entry[2].read_bytes() for entry in candidates.values()})
        try:
            for data,_,target in candidates.values():
                target.write_bytes(data)
            write(config_path,config)
            write(context_path,contexts)
            write(recipe_path,recipe)
            shutil.copy2(ROOT/'android/Assets/Editor/LabBuild.cs',editor_path)
        except Exception:
            for path,data in backups.items():
                path.write_bytes(data)
            raise
        result = {'success':True,'input_id':input_id,'stages':pending,
                  'runtime_graph_roots_added':added_graphs,
                  'scene_sha256':{name:sha(candidates[name][2]) for name in pending},
                  'config_sha256':sha(config_path),'contexts_sha256':sha(context_path),
                  'recipe_sha256':sha(recipe_path),'editor_sha256':sha(editor_path),
                  'evidence':str(out.relative_to(ROOT))}
        write(out/'result.json',result)
        write(WORK/'experiments/stage-variants/latest.json',result)
        return result
    except Exception as error:
        write(out/'failure.json',{'error':str(error),'input_id':input_id,
                                  'staged_scene_files':[name for name in candidates]})
        raise
    finally:
        recipe_path.write_bytes(recipe_before) if not (out/'result.json').exists() else None
        if temporary.exists():
            shutil.rmtree(temporary)
