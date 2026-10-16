"""Stage measured source scenes selected by the original stage groups."""
import gzip
import json
import re
import shutil
from pathlib import Path

from common import ROOT, WORK, now, read, sha, write
from source_scene_candidate import SCENES

VARIANTS = {
    'blackbeach': '9672ae28cd6b03b2c7533f6084607595858708a148ee5e66114fc61f70c43a58',
    'blackbeach2': '39ec58020c56dac7275538d4f529383b0dc73615a28c03e2273e92c12467d93a',
    'golemplains2': 'f3dcbfa1cf86a3e1bc3d42642b199114ce403543a41f4c00ccf5410e30ad297f',
    'goolake': 'edbd7dfa00ab03ea1d1cfa723afea5f0985ccfc6820d5ff86da0c971d3011b6d',
    'rootjungle': '9208b430b51ff6feae9c687fc7e35c0bd103e5749fefff5759c8f2ca4237d1c3',
    'lakes': 'bf03c16ab1a2c9dcafba759917e0b1224f8bdd3dca5da719d30c8fc72f37f2e2',
    'goldshores': 'c01ab9ea9abf8145fb0f6322966730061afaf2d5281f610cad61f4eac7b84338',
    'ancientloft': 'ec03cfb0a9b745ed57d3d86af750038f5017edd8c03f9aaf63d19d1f009f799a',
    'snowyforest': 'cec55d6208a04d34916bbf6baa14d924d6bcb435a816a51806264fbe6fef00a1',
    'sulfurpools': '95cc78087b9347763ca2b01646724e0a0b5052f77c2ceceda124919cd75595dd',
    'habitat': 'b789fc3d388fcfc1987cb18e415b4aa2531e79db8656572312d0961add048bd7',
    'habitatfall': '843cb9306b5376906f143e5fc392dd329ca8aedde0b3a5973efadc3eec55ddbd',
    'helminthroost': '0b6094c1a18911e0e6e7dce90002061a52fba4840f4952cde9673fe48a7aeff8',
    'lakesnight': '0c7d11679300d123c323a4b4c9d8444cbb28dd280da30173f8f0e8f9720bf59a',
    'village': '7af265fa4ce228a6c3cdbfd9e77d73db1b3d491de4eb787c87f76e74ed2d962c',
    'villagenight': 'c833bafe1c6a2827f28455ca4a0903914923c99b6c652581e57426ee617fbd05',
}
SOURCE_SHA256 = {
    'lakes': '36782d7d6eaf8ce6eb2fb0e1cb321a7fc6e9b38cb41aee196c0ed20acaa765e4',
    'ancientloft': '258b21f2367240d1d2e4804d44e421e3f9cdc1ab8417c2aa866876a58a0a7b3f',
    'snowyforest': 'b104f59af63c89ee1320d6ecb1cd4c8a8ed20145dc5a5fbc928ba140824b0505',
    'sulfurpools': '9a5a64ffa4dc5ff166d9197ee28a80bbc97ecbf26f62d5e2cec20e17936d0f53',
    'habitat': '7874db0a03a060120d8679287c6850fce348f61c994e289724c02d08168ac519',
    'habitatfall': 'cac8f86f449dc6f13fa6d79bac3fb047531d022a7bdb9a146b3e645cbcf94f3a',
    'helminthroost': 'f0f1cb671464f1c2d4f98ab46c6bedcc21c0ea9a2b1e303ee24467c6c7b97409',
    'lakesnight': '33aa6fa8a260c1579e6649cfc2c33bc3f97df4928242672eb497f5da7cf5e67c',
    'village': '7d1e5e7ea10dd73df9418a0a9fcca9828ae9749292bb3899b022bfc5202891a2',
    'villagenight': '45e1672cff6ad69d46b18b659d02cb828e061d2f6b98e6e7bc9dae900283f07d',
}


def scene_root(name):
    return SCENES[name]


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
    pending = [name for name in VARIANTS if name not in names]
    staged = [name for name in VARIANTS if name in names]
    if all(sha(project/'Assets/WholeGame/RoR2'/scene_root(name)/'Scenes'/name/(name+'.unity')) == VARIANTS[name]
           for name in staged):
        if not pending:
            for row in config['integratedStages']:
                if row['name'] in VARIANTS:
                    row['previewNames'] = sorted(row['previewNames'])
            added = include_runtime_graph_roots(config,recipe,project,accepted_files)
            write(config_path,config)
            if added:write(recipe_path,recipe)
            return {'success':True, 'already_staged':True, 'stages':staged,'runtime_graph_roots_added':added}
    else:
        raise RuntimeError('Previously staged scene variant changed; review before regenerating')
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
        for name in pending:
            digest = VARIANTS[name]
            root = scene_root(name)
            target = project/'Assets/WholeGame/RoR2'/root/'Scenes'/name/(name+'.unity')
            source = export/'Assets/RoR2'/root/'Scenes'/name/(name+'.unity')
            if not target.is_file() or not source.is_file():
                raise RuntimeError('Accepted scene source is missing: '+name)
            if name in SOURCE_SHA256 and sha(source) != SOURCE_SHA256[name]:
                raise RuntimeError('Original stage source changed; review before conversion: '+name)
            if sha(target) == digest:
                raise RuntimeError('Converted scene exists outside the stage-variant configuration: '+name)
            with gzip.open(originals/(name+'.unity.gz'),'wb',compresslevel=6) as archive:
                archive.write(target.read_bytes())
            spec = stage_first_stage_geometry(project/'Assets/LabLoadingScene',out,
                    original_name=True,scene_name=name,map_zones=True,presentation=True,billboards=True,scene_root=root)
            generated = temporary/(name+'.unity')
            if sha(generated) != digest:
                raise RuntimeError('Recovered scene variant differs from the measured source projection: '+name)
            checked,counts,removed = scene_contract(source.read_text(),generated.read_text())
            if checked != generated.read_text() or removed:
                raise RuntimeError('Recovered scene has an unexpected callback or network owner: '+name)
            list_fields = ('mapZoneActiveNames','emptyMeshPaths','emptyColliderPaths')
            if sorted(spec['previewNames']) != counts['previewNames'] or any(spec[key] != counts[key] for key in ('previewCallbacks','mapZoneCount','mapZoneNetworkObjects')) or any(sorted(spec[key]) != sorted(counts[key]) for key in list_fields):
                raise RuntimeError('Scene contract report differs from source projection: '+name)
            spec['previewNames'] = counts['previewNames']
            for key in list_fields:spec[key] = sorted(spec[key])
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
                                    'previous_sha256':sha(target),'generated_sha256':sha(generated),
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
