"""Recover the Moon mission into the continuing composition; inputs stay ignored."""
from common import *
import re
import shutil

def unity_name(value):
    if value.startswith("'") and value.endswith("'"):return value[1:-1].replace("''", "'")
    if value.startswith('"'):return json.loads(value)
    return value

def stage_moon(stage, previous, out, spec):
    from scene_closure import REFERENCE
    export = ROOT/read(WORK/'config/reconstruction.json')['projects'][0]
    source = export/'Assets/RoR2/Base/Scenes/moon2/moon2.unity'
    original = source.read_text()
    blocks = re.split(r'(?=^--- !u!)', original, flags=re.M)[1:]
    identities = {}
    for row in (WORK/'moon-script-identities.txt').read_text().splitlines():
        fid, guid, kind = row.split('|')
        identities[(fid, guid)] = kind
    # Source scripts are measured from the preserved assembly, not guessed from names.
    def kind(block):
        match = re.search(r'm_Script: \{fileID: (-?\d+), guid: ([a-f0-9]+)', block)
        return identities.get((match[1], match[2]), '') if match else ''
    objects = {re.match(r'--- !u!1 &(-?\d+)', b)[1]: unity_name(re.search(r'^  m_Name: (.*)$', b, re.M)[1])
               for b in blocks if b.startswith('--- !u!1 ')}
    mission_names = {'SceneInfo', 'MoonMissionController', 'MoonBatteryMissionController',
                     'BrotherMissionController', 'EscapeSequenceController', 'SceneObjectToggleGroup', 'Director'}
    mission_scripts = {'RoR2.SceneInfo', 'RoR2.ClassicStageInfo', 'RoR2.MoonMissionController', 'RoR2.MoonBatteryMissionController',
                       'RoR2.SceneObjectToggleGroup', 'RoR2.EscapeSequenceController',
                       'RoR2.AllPlayersTrigger', 'RoR2.OnPlayerEnterEvent', 'RoR2.Navigation.GateStateSetter',
                       'RoR2.MapZone', 'RoR2.JumpVolume'}
    contextual_scripts = {'RoR2.EntityStateMachine', 'RoR2.NetworkStateMachine', 'ChildLocator',
                          'RoR2.ModelLocator', 'RoR2.HoldoutZoneController', 'RoR2.PurchaseInteraction',
                          'RoR2.GenericInteraction', 'RoR2.CombatDirector', 'RoR2.BossGroup',
                          'RoR2.CombatSquad', 'RoR2.ScriptedCombatEncounter', 'RoR2.PhaseCounter'}
    retained = []
    for block in blocks:
        if not block.startswith('--- !u!114 '): continue
        go = re.search(r'm_GameObject: \{fileID: (-?\d+)\}', block)[1]
        name = objects[go]
        context = name in mission_names or name.startswith(('MoonBattery', 'MoonElevator', 'BrotherEncounter')) or name == 'mdlMoonBattery' or name == 'mdlMoonElevator'
        if kind(block) in mission_scripts or (context and kind(block) in contextual_scripts): retained.append(block)
    owners = {re.search(r'm_GameObject: \{fileID: (-?\d+)\}', b)[1] for b in retained}
    # PurchaseInteraction requires Highlight. Omitting its serialized dependency
    # makes Unity insert an unreceipted component while importing the scene.
    purchase_owners = {re.search(r'm_GameObject: \{fileID: (-?\d+)\}', b)[1]
                       for b in retained if kind(b) == 'RoR2.PurchaseInteraction'}
    highlights = [b for b in blocks if b.startswith('--- !u!114 ') and kind(b) == 'RoR2.Highlight'
                  and re.search(r'm_GameObject: \{fileID: (-?\d+)\}', b)[1] in purchase_owners]
    if len(highlights) != len(purchase_owners):
        raise RuntimeError('Original Moon purchase Highlight contract differs')
    retained += highlights
    retained += [b for b in blocks if b.startswith('--- !u!114 ') and kind(b)=='RoR2.EntityLocator'
                 and re.search(r'entity: \{fileID: (-?\d+)\}', b)
                 and re.search(r'entity: \{fileID: (-?\d+)\}', b)[1] in owners]
    # NetworkIdentity and trigger rigidbodies are source serialization, not fabricated IDs.
    retained += [b for b in blocks if b.startswith('--- !u!114 ') and
                 'm_Script: {fileID: 372142912, guid: d382a022563c7517aadbc92ca1060016' in b and
                 re.search(r'm_GameObject: \{fileID: (-?\d+)\}', b)[1] in owners]
    retained += [b for b in blocks if b.startswith('--- !u!54 ') and
                 re.search(r'm_GameObject: \{fileID: (-?\d+)\}', b)[1] in owners]
    by_id={re.match(r'--- !u!\d+ &(-?\d+)',b)[1]:b for b in blocks}
    retained_ids={re.match(r'--- !u!\d+ &(-?\d+)',b)[1] for b in retained}
    missing_scripts={fid for b in retained for fid in re.findall(r'\{fileID: (-?\d+)\}',b)
                     if fid in by_id and by_id[fid].startswith('--- !u!114 ') and fid not in retained_ids}
    if missing_scripts:raise RuntimeError('Moon mission references omitted source scripts: '+str(sorted(missing_scripts)))
    required = {'RoR2.ClassicStageInfo': 1, 'RoR2.MoonBatteryMissionController': 1, 'RoR2.ScriptedCombatEncounter': 4,
                'RoR2.EscapeSequenceController': 1, 'RoR2.AllPlayersTrigger': 1}
    for type_name, count in required.items():
        if sum(kind(b) == type_name for b in retained) != count:
            raise RuntimeError('Original Moon mission contract differs: '+type_name)
    dest = stage/'StageGeometry/moon2.unity'
    generated = dest.read_text()
    additions = {}
    for block in retained:
        go = re.search(r'm_GameObject: \{fileID: (-?\d+)\}', block)[1]
        additions.setdefault(go, []).append(re.match(r'--- !u!\d+ &(-?\d+)', block)[1])
    for go, ids in additions.items():
        pattern = r'(^--- !u!1 &'+go+r'\n.*?)(?=^--- !u!|\Z)'
        generated, count = re.subn(pattern, lambda m: m[0].replace('  m_Component:\n',
            '  m_Component:\n'+''.join('  - component: {fileID: '+fid+'}\n' for fid in ids), 1), generated, flags=re.M|re.S)
        if count != 1: raise RuntimeError('Moon component owner missing')
    generated += ''.join(retained)
    # Defer whole scene activation until converted materials and source SceneInfo are ready.
    roots = {re.search(r'm_GameObject: \{fileID: (-?\d+)\}', b)[1] for b in blocks
             if b.startswith(('--- !u!4 ', '--- !u!224 ')) and '  m_Father: {fileID: 0}' in b}
    active_roots = []
    for go in roots:
        pattern = r'(^--- !u!1 &'+go+r'\n.*?)(?=^--- !u!|\Z)'
        def defer(match):
            if '  m_IsActive: 1' in match[0]: active_roots.append(objects[go])
            return match[0].replace('  m_IsActive: 1', '  m_IsActive: 0')
        generated = re.sub(pattern, defer, generated, flags=re.M|re.S)
    dest.write_text(generated)
    from moon_scene import restore_pillar_beams, restore_moon_gravity, restore_moon_escape
    write(out/'original-moon-beam-restoration.json', restore_pillar_beams(source, dest))
    write(out/'original-moon-gravity-restoration.json',
          restore_moon_gravity(source, dest, WORK/'moon-script-identities.txt'))
    escape = restore_moon_escape(source, dest, WORK/'moon-script-identities.txt')
    write(out/'original-moon-escape-restoration.json', escape)
    index, existing = {}, {}
    for base, target in [(export/'Assets', index), (stage, existing)]:
        for meta in base.rglob('*.meta'):
            match = re.search(r'^guid: ([a-f0-9]{32})', meta.read_text(errors='replace'), re.M)
            if match: target[match[1]] = Path(str(meta)[:-5])
    roots_to_copy = list((source.parent).rglob('EntityStates.*.asset'))
    # Commencement shares mission/state configuration with the original moon folder.
    roots_to_copy += list((export/'Assets/RoR2/Base/Scenes/moon').rglob('EntityStates.*.asset'))
    # Referenced drop-table metadata must be cataloged even when it is not loot.
    item_sources = [export/'Assets/RoR2'/region/'Items'/name/(name+'.asset')
                    for region, name in [('DLC1','VoidMegaCrabItem'), ('DLC3','MasterCore'),
                    ('DLC3','MasterBattery'), ('Base','ArtifactKey'), ('DLC3','PowerCube'),
                    ('DLC3','PowerPyramid'), ('DLC3','PowerOrbSphere')]]
    buff_sources = [export/'Assets/RoR2/Base/Elites/EliteLunar/bdEliteLunar.asset',
                    export/'Assets/RoR2/Base/Common/Buffs/Cripple/bdCripple.asset']
    equipment_sources = [export/'Assets/RoR2/Base/Elites/EliteLunar/EliteLunarEquipment.asset']
    roots_to_copy += item_sources + buff_sources + equipment_sources
    actor_roots = []
    typed_rows = [x.split('|') for x in (WORK/'moon-address-query.txt').read_text().splitlines()]
    subobject_provenance=[];absent_inherited_renderers=[]
    def addressed(key, type_name, sub=''):
        rows = [x for x in typed_rows if len(x)>=3 and x[0]==key and x[2]==type_name]
        if len(rows)!=1: raise RuntimeError('Moon typed address differs: '+key+' '+type_name)
        src = export/rows[0][1]
        if sub:
            unity_class={'UnityEngine.Mesh':43,'UnityEngine.Avatar':90}[type_name]
            candidates=[p for p in src.parent.glob('*.asset') if re.search(r'^--- !u!'+str(unity_class)+r' ',p.read_text(errors='replace'),re.M)
                        and re.search(r'^  m_Name: '+re.escape(sub)+r'$',p.read_text(errors='replace'),re.M)]
            if len(candidates)>1:
                # AssetRipper exports each FBX hierarchy as its own prefab. Shared
                # mesh names in the folder do not identify the owning model.
                model=src.with_suffix('.prefab')
                if not model.exists():raise RuntimeError('Moon subobject owner missing: '+src.name)
                owner=model.read_text()
                candidates=[p for p in candidates if re.search(r'^guid: ([a-f0-9]{32})',Path(str(p)+'.meta').read_text(),re.M)[1] in owner]
                subobject_provenance.append(dict(key=key,subobject=sub,model=str(model.relative_to(export)),model_sha256=sha(model)))
            if len(candidates)!=1:raise RuntimeError('Moon typed subobject ambiguous: '+sub)
            src=candidates[0]
            subobject_provenance.append(dict(key=key,subobject=sub,asset=str(src.relative_to(export)),sha256=sha(src)))
        if not src.exists(): raise RuntimeError('Moon typed source missing: '+str(src.relative_to(export)))
        return src
    for family in ['Brother/Brother', 'Brother/BrotherHurt', 'LunarGolem', 'LunarWisp', 'LunarExploder']:
        folder = export/'Assets/RoR2/Base/Characters'/family
        name = folder.name
        body = folder/(name+'Body.prefab'); master = folder/(name+'Master.prefab'); card = folder/('csc'+name+'.asset')
        body_text = body.read_text()
        def inherited_params(skin, trail=()):
            if skin in trail:raise RuntimeError('Original Moon skin inheritance cycle')
            text=skin.read_text();base=text.split('  baseSkins:')[1].split('  icon:')[0]
            parents=[index[g] for _,g,_ in REFERENCE.findall(base)]
            own=skin.with_name(skin.stem+'_params.asset')
            return ''.join(inherited_params(x,trail+(skin,)) for x in parents)+own.read_text()
        params=inherited_params(next(folder.glob('*Default.asset')))
        actor = dict(name=name, body=body, master=master, card=card)
        for label, field, type_name in [('avatar','_avatarAddress','UnityEngine.Avatar'),('controller','_animatorControllerAddress','UnityEngine.RuntimeAnimatorController')]:
            address = re.search(field+r':\n((?:    .*\n){3})', body_text)[1]
            actor[label] = addressed(re.search(r'm_AssetGUID: ([a-f0-9]{32})',address)[1],type_name,
                                     re.search(r'm_SubObjectName: (.*)',address)[1] if label=='avatar' else '')
        prefab_cache={}
        def renderer_path(fid,guid):
            if guid not in prefab_cache:
                prefab_cache[guid]={re.match(r'--- !u!\d+ &(-?\d+)',b)[1]:b for b in re.split(r'(?=^--- !u!)',index[guid].read_text(),flags=re.M)[1:]}
            body_blocks=prefab_cache[guid]
            def object_path(go):
                block=body_blocks[go];obj_name=unity_name(re.search(r'^  m_Name: (.*)$',block,re.M)[1])
                transform=next(body_blocks[x] for x in re.findall(r'component: \{fileID: (-?\d+)\}',block) if body_blocks[x].startswith(('--- !u!4 ','--- !u!224 ')))
                parent=re.search(r'm_Father: \{fileID: (-?\d+)\}',transform)[1]
                return obj_name if parent=='0' else object_path(re.search(r'm_GameObject: \{fileID: (-?\d+)\}',body_blocks[parent])[1])+'/'+obj_name
            go=re.search(r'm_GameObject: \{fileID: (-?\d+)\}',body_blocks[fid])[1]
            return object_path(go).split('/',1)[1]
        renderer_materials={};renderer_meshes={};renderer_sources={}
        for fid,guid,key in re.findall(r'renderer: \{fileID: (-?\d+), guid: ([a-f0-9]{32}), type: \d+\}\n    defaultMaterialAddress:\n      m_AssetGUID: ([a-f0-9]{32})',params):
            path=renderer_path(fid,guid);renderer_materials[path]=addressed(key,'UnityEngine.Material');renderer_sources[path]=guid
        for fid,guid,key,sub in re.findall(r'renderer: \{fileID: (-?\d+), guid: ([a-f0-9]{32}), type: \d+\}\n    meshAddress:\n      m_AssetGUID: ([a-f0-9]{32})\n      m_SubObjectName: ([^\n]+)',params):
            renderer_meshes[renderer_path(fid,guid)]=addressed(key,'UnityEngine.Mesh',sub)
        own_guid=re.search(r'^guid: ([a-f0-9]{32})',Path(str(body)+'.meta').read_text(),re.M)[1]
        own_renderers={renderer_path(re.match(r'--- !u!\d+ &(-?\d+)',b)[1],own_guid) for b in re.split(r'(?=^--- !u!)',body_text,flags=re.M)[1:]
                       if int(re.match(r'--- !u!(\d+)',b)[1]) in {23,96,120,137,199,212,222}}
        for path in set(renderer_materials)-own_renderers:
            if renderer_sources[path]==own_guid or path in renderer_meshes:
                raise RuntimeError('Moon own renderer or required mesh missing: '+name+'/'+path)
            # Original RuntimeSkin.ApplyAsync warns and omits a renderer absent in
            # the derived body. Match that source behavior without inventing one.
            absent_inherited_renderers.append(dict(actor=name,path=path,source_prefab_guid=renderer_sources[path],target_body_sha256=sha(body)))
        actor['bindings']=[dict(path=path,mesh=renderer_meshes.get(path),material=material) for path,material in renderer_materials.items() if path in own_renderers]
        if not renderer_meshes:raise RuntimeError('Moon default mesh bindings missing: '+name)
        roots_to_copy += [x for k,x in actor.items() if k not in {'name','bindings'}]
        roots_to_copy += [v for binding in actor['bindings'] for k,v in binding.items() if isinstance(v,Path)]
        roots_to_copy += list(renderer_materials.values())
        actor_roots.append(actor)
    for family in ['Brother', 'LunarGolem', 'LunarWisp', 'LunarExploder']:
        folder = export/'Assets/RoR2/Base/Characters'/family
        roots_to_copy += list(folder.rglob('EntityStates.*.asset'))
    # Deferred body visuals are selected by the original typed catalog query.
    query = (WORK/'moon-address-query.txt').read_text().splitlines()
    for row in query:
        parts = row.split('|')
        if len(parts) >= 3 and (export/parts[1]).exists(): roots_to_copy.append(export/parts[1])
    moon_scene=export/'Assets/RoR2/Base/Scenes/moon2/moon2.asset'
    roots_to_copy.append(moon_scene)
    pending = roots_to_copy + [index[g] for _, g, _ in REFERENCE.findall(''.join(retained))
                              if g and not g.startswith('0000000000000000')]
    pending += [index[g] for g in escape['external_guids'] if not g.startswith('0000000000000000')]
    seen, rows, staged = set(), [], {}
    remaps = {x['from']: x['to'] for x in previous.get('ui_remaps', [])}
    while pending:
        src = pending.pop()
        if src in seen: continue
        seen.add(src)
        guid = re.search(r'^guid: ([a-f0-9]{32})', Path(str(src)+'.meta').read_text(), re.M)[1]
        if src.suffix == '.dll':
            if src.name == 'UnityEngine.UI.dll' and remaps: continue
            if guid not in existing: raise RuntimeError('Unprovided Moon assembly: '+src.name)
            continue
        if src.suffix == '.unity': raise RuntimeError('Moon dependency unexpectedly loads another scene')
        dst = existing.get(guid, stage/'MoonClosure'/src.relative_to(export/'Assets'))
        if guid not in existing:
            dst.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(src, dst)
            shutil.copy2(Path(str(src)+'.meta'), Path(str(dst)+'.meta')); existing[guid] = dst
        staged[src] = str(dst.relative_to(WORK/'lab-project'))
        rows.append(dict(source=str(src.relative_to(export)), source_sha256=sha(src), staged=staged[src], bytes=src.stat().st_size))
        if src.read_bytes()[:5] != b'%YAML': continue
        text = src.read_text()
        for g in {g for _, g, _ in REFERENCE.findall(text) if g and not g.startswith('0000000000000000')}:
            if g not in index: raise RuntimeError('Unresolved Moon GUID: '+src.name)
            pending.append(index[g])
        if any(old in text for old in remaps):
            if dst.read_bytes()[:5]!=b'%YAML':
                raise RuntimeError('Moon UI remap requires a text asset: '+str(src.relative_to(export)))
            generated_asset = dst.read_text()
            for old, new in remaps.items(): generated_asset = generated_asset.replace(old, new)
            dst.write_text(generated_asset)
    recipe = read(WORK/'scene-probe-build.json')
    assets = [staged[x] for x in roots_to_copy if x in staged]
    pillar_rows = [x for x in typed_rows if len(x)==4 and x[3]=='Prefabs/PositionIndicators/PillarChargingPositionIndicator' and x[2]=='UnityEngine.GameObject']
    if len(pillar_rows)!=1:raise RuntimeError('Original pillar indicator location changed')
    pillar=staged[export/pillar_rows[0][1]]
    support_paths = ['Prefabs/Projectiles/LunarMissileProjectile',
                     'Prefabs/TemporaryVisualEffects/CrippleEffect',
                     'SpawnCards/HelperPrefab',
                     'Prefabs/NetworkedObjects/ItemStealController',
                     'Prefabs/Effects/OrbEffects/ItemTransferOrbEffect']
    support_rows = []
    for path in support_paths:
        matches = [x for x in typed_rows if len(x)==4 and x[3]==path and x[2]=='UnityEngine.GameObject']
        if len(matches)!=1:raise RuntimeError('Original Moon support location differs: '+path)
        row=matches[0];support_rows.append(dict(path=path,key=row[0],asset=staged[export/row[1]].lower()))
    supports=[pillar]+[staged[export/x[1]] for x in typed_rows
                      if len(x)==4 and x[3] in support_paths and x[2]=='UnityEngine.GameObject']
    recipe['objectiveSupportAssets']=list(dict.fromkeys(recipe['objectiveSupportAssets']+supports))
    assets=[x for x in assets if x not in supports]
    recipe['prefabAssets'] = list(dict.fromkeys(recipe['prefabAssets']+assets))
    write(WORK/'scene-probe-build.json', recipe)
    configs = [staged[x].lower() for x in roots_to_copy if x.name.startswith('EntityStates.')]
    spec.update(moonMission=True, activeRoots=active_roots,
                missionComponents=len(re.findall(r'^--- !u!114 ', dest.read_text(), re.M)))
    write(out/'moon-mission-contract.json', dict(source_sha256=sha(source), generated_sha256=sha(dest),
        components=[dict(id=re.match(r'--- !u!\d+ &(-?\d+)', b)[1], type=kind(b)) for b in retained],
        closure=rows, bytes=sum(x['bytes'] for x in rows), deferred_active_roots=active_roots,
        subobject_provenance=subobject_provenance,absent_inherited_renderers=absent_inherited_renderers,
        prior_art='Pinned Starstorm2 a9a4badd SceneAssetCollection/SlateMines preserves scene identities; R2API.Director f539511e separates stage and director activity. Original MoonBatteryMissionController, scripted encounters, trigger callbacks and escape wiring govern progression. No source implementation copied.',
        scope='Original recovered Moon mission wiring staged into whole game; source scene activation deferred for owned Android material/context setup. No battery/phase/escape/victory completion fabricated.'))
    actor_specs=[]
    for actor in actor_roots:
        row={k:staged[v].lower() for k,v in actor.items() if k not in {'name','bindings'}}
        row['name']=actor['name'];row['bindings']=[dict(path=b['path'],mesh=staged[b['mesh']].lower() if b['mesh'] else '',material=staged[b['material']].lower()) for b in actor['bindings']]
        actor_specs.append(row)
    moon_scene=export/'Assets/RoR2/Base/Scenes/moon2/moon2.asset'
    if moon_scene not in staged:raise RuntimeError('Recovered Moon SceneDef missing from source closure')
    recipe['prefabAssets']=list(dict.fromkeys(recipe['prefabAssets']+[staged[moon_scene]]))
    write(WORK/'scene-probe-build.json',recipe)
    return dict(configs=configs,actors=actor_specs,pillar=pillar.lower(),pillarKey=pillar_rows[0][0],sceneDef=staged[moon_scene].lower(),
                catalog=dict(items=[staged[x].lower() for x in item_sources],
                             buffs=[staged[x].lower() for x in buff_sources],
                             equipment=[staged[x].lower() for x in equipment_sources]),supports=support_rows)
