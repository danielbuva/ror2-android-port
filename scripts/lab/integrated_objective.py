"""Content/context for the composed teleporter loop; all derived inputs remain ignored."""
from common import *
import re
import shutil
import hashlib


def transform_optional_presentation(stage, out, attempt):
    from boundaries import probe_tool
    original=stage/'Plugins/RoR2.dll'
    expected=attempt['original_assemblies']['RoR2.dll']
    if sha(original)!=expected:
        raise RuntimeError('Optional presentation requires verified original DLL')
    candidate=out/'RoR2.optional-presentation.dll'
    report=json.loads(run(probe_tool()+['--optional-presentation-guard',original,candidate,expected,game()/'Risk of Rain 2_Data/Managed'],timeout=120).stdout)
    shutil.copy2(original,out/'RoR2.original.dll');shutil.copy2(candidate,original)
    write(out/'optional-presentation-transformation.json',report)
    attempt['transformed_assemblies']={'RoR2.dll':report['output_sha256']}


def stage_classic_run_settings(out):
    """Recover the serialized loop-reset contract omitted by an AddComponent Run."""
    export=ROOT/read(WORK/'config/reconstruction.json')['projects'][0]
    source=export/'Assets/RoR2/Base/GameModes/ClassicRun/ClassicRun.prefab'
    lines=source.read_text().splitlines()
    indices=[i for i,line in enumerate(lines) if line.startswith('  EventFlagsToResetOnLoop:')]
    if len(indices)!=1:raise RuntimeError('Original ClassicRun loop-reset field is missing or ambiguous')
    index=indices[0];header=lines[index];flags=[]
    if header=='  EventFlagsToResetOnLoop:':
        for line in lines[index+1:]:
            if not line.startswith('  - '):break
            value=line[4:]
            if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*',value):raise RuntimeError('Unparsed original loop-reset flag; review input')
            flags.append(value)
        if not flags:raise RuntimeError('Original loop-reset list has no entries; review input')
    elif header!='  EventFlagsToResetOnLoop: []':raise RuntimeError('Unparsed original loop-reset list; review input')
    write(out/'classic-run-settings.json',{'source':str(source.relative_to(export)),'source_sha256':sha(source),'event_flags':flags,'scope':'Original serialized event reset names on the composed Run; no event injected or gameplay reset skipped.'})
    return {'runEventFlagsToResetOnLoop':flags}


def stage_objective(stage, previous, out):
    run_settings=stage_classic_run_settings(out)
    from scene_closure import REFERENCE
    export = ROOT/read(WORK/'config/reconstruction.json')['projects'][0]
    checkpoint = read(WORK/'checkpoints/LAST_KNOWN_GOOD_INTEGRATED_WORLD.json')
    query_path = ROOT/checkpoint['evidence']/'next-objective-catalog-query.json'
    query = read(query_path)
    if query.get('error') or query.get('missing'):
        raise RuntimeError('Objective runtime catalog query incomplete')
    index, existing = {}, {}
    for base, target in [(export/'Assets', index), (stage, existing)]:
        for meta in base.rglob('*.meta'):
            match = re.search(r'^guid: ([a-f0-9]{32})', meta.read_text(errors='replace'), re.M)
            if match:
                target[match[1]] = Path(str(meta)[:-5])
    runtime = {row['key']: export/row['internalId'] for row in query['locations']
               if (export/row['internalId']).exists()}
    roots = {'teleporterAsset': export/'Assets/RoR2/Base/Interactables/Teleporters/Teleporter1/Teleporter1.prefab',
             'lunarTeleporterAsset': export/'Assets/RoR2/Base/Interactables/Teleporters/LunarTeleporter/LunarTeleporter Variant.prefab',
             'objectiveTMPSettingsAsset': export/'Assets/TextMesh Pro/FormerResources/TMP Settings.asset',
             'objectiveStunAsset': export/'Assets/RoR2/Base/Common/VFX/Stuns/StunVfx.prefab',
             'teleporterIndicatorAsset': export/'Assets/RoR2/Base/Interactables/Teleporters/TeleporterChargingPositionIndicator.prefab'}
    support_names=['BeetleWardOrbEffect','BeetleWard','TeleportOutController','ChainLightningOrbEffect']
    support_paths=['Prefabs/Effects/OrbEffects/BeetleWardOrbEffect','Prefabs/NetworkedObjects/BeetleWard','Prefabs/NetworkedObjects/TeleportOutController','Prefabs/Effects/OrbEffects/LightningOrbEffect']
    support_keys=['89ddb892b8343654ab59d9176e270d49','de83659161b919844b1309bc9aaa3c71','fc6479a19530c3f449ef8056667582b2','32d422991ab4bd1479b80aed53b2bfdb']
    query_rows=(WORK/'objective-support-query.txt').read_text().splitlines()+['|'.join(x.split('|')[1:]) for x in (WORK/'loot-orb-query.txt').read_text().splitlines()]
    support_roots=[]
    for name,key in zip(support_names,support_keys):
        rows=[x.split('|') for x in query_rows if x.startswith(key+'|')]
        if len(rows)!=1 or rows[0][2]!='UnityEngine.GameObject':raise RuntimeError('Original objective support typed location changed: '+name)
        src=export/rows[0][1]
        if src.name!=name+'.prefab':raise RuntimeError('Original support source identity changed')
        root='support'+name;roots[root]=src;support_roots.append(root)
    roots['objectiveWardBuffAsset']=export/'Assets/RoR2/Base/Characters/BeetleGroup/bdBeetleJuice.asset'
    roots['objectiveWardConfig']=export/'Assets/RoR2/Base/Characters/BeetleGroup/BeetleWard/EntityStates.BeetleQueenMonster.BeetleWardDeath.asset'
    ward_rows=[x.split('|') for x in (WORK/'ward-catalog-query.txt').read_text().splitlines()]
    ward_folder=roots['objectiveWardConfig'].parent
    for name,key,kind in [('Controller','1ac73abb611d7f445b00eb929b22648f','UnityEngine.RuntimeAnimatorController'),('Material','29bd00d772ad334439c61187f22544f6','UnityEngine.Material'),('SphereMaterial','c9cd3f79c6f67f447920a93b72b7fe64','UnityEngine.Material')]:
        matches=[x for x in ward_rows if x[0]==key and x[2]==kind]
        if len(matches)!=1:raise RuntimeError('Original ward typed identity changed: '+name)
        roots['ward'+name]=export/matches[0][1]
    if len([x for x in ward_rows if x[0]=='7a24245928ff6224f8f7cee0b382d5ac' and x[2]=='UnityEngine.Avatar'])!=1:raise RuntimeError('Ward avatar identity missing')
    roots['wardAvatar']=ward_folder/'mdlBeetleWardAvatar.asset'
    roots['wardMesh']=ward_folder/'BeetleQueenWardMesh.asset'
    actors = []
    configs = ['objectiveWardConfig']
    for family, body_name in [('BeetleQueen', 'BeetleQueen2Body'), ('BeetleGuard', 'BeetleGuardBody')]:
        folder = export/'Assets/RoR2/Base/Characters/BeetleGroup'/family
        prefix = family.lower()
        roots[prefix+'Body'] = folder/(body_name+'.prefab')
        roots[prefix+'Master'] = folder/(family+'Master.prefab')
        roots[prefix+'Card'] = folder/('csc'+family+'.asset')
        body = roots[prefix+'Body'].read_text()
        for label, field, kind in [('Controller', '_animatorControllerAddress', 'UnityEngine.RuntimeAnimatorController'),
                                   ('Avatar', '_avatarAddress', 'UnityEngine.Avatar')]:
            block = re.search(field+r':\n((?:    .*\n){3})', body)[1]
            key = re.search(r'm_AssetGUID: ([a-f0-9]{32})', block)[1]
            locations = [x for x in query['locations'] if x['key']==key and x['type']==kind]
            if len(locations)!=1:
                raise RuntimeError('Objective actor typed address changed: '+field)
            src = export/locations[0]['internalId']
            if kind=='UnityEngine.Avatar':
                sub = re.search(r'm_SubObjectName: (.*)', block)[1]
                candidates = [p for p in src.parent.glob('*.asset') if re.search(r'^--- !u!90 ', p.read_text(errors='replace'), re.M)
                              and re.search(r'^  m_Name: '+re.escape(sub)+r'$', p.read_text(errors='replace'), re.M)]
                if len(candidates)!=1:
                    raise RuntimeError('Objective avatar subobject missing: '+sub)
                src = candidates[0]
            roots[prefix+label] = src
        params = next(folder.glob('skin*Default_params.asset')).read_text()
        material = re.search(r'defaultMaterialAddress:\n      m_AssetGUID: ([a-f0-9]{32})', params)[1]
        roots[prefix+'Material'] = runtime[material]
        mesh_part = params.split('  meshReplacements:')[1].split('  projectileGhostReplacements:')[0]
        meshes = re.findall(r'm_AssetGUID: ([a-f0-9]{32})\s+m_SubObjectName: (\S+)', mesh_part)
        if len(meshes)!=1:
            raise RuntimeError('Objective default mesh contract changed: '+family)
        mesh_guid, mesh_name = meshes[0]
        locations = [x for x in query['locations'] if x['key']==mesh_guid and x['type']=='UnityEngine.Mesh']
        if len(locations)!=1:
            raise RuntimeError('Objective mesh typed location missing: '+family)
        mesh = (export/locations[0]['internalId']).parent/(mesh_name+'.asset')
        mesh_text = mesh.read_text()
        if not re.search(r'^--- !u!43 ',mesh_text,re.M) or not re.search(r'^  m_Name: '+re.escape(mesh_name)+r'$',mesh_text,re.M):
            raise RuntimeError('Objective mesh subobject identity changed: '+family)
        roots[prefix+'Mesh'] = mesh
        for config in folder.rglob('EntityStates.*.asset'):
            key = 'config'+str(len(configs)); roots[key]=config; configs.append(key)
        actors.append(prefix)
    item_names = ['WardOnLevel', 'FocusConvergence', 'TPHealingNova', 'BeetleGland', 'Ghost', 'Knurl', 'SprintBonus', 'FlatHealth']
    for name in item_names:
        candidates = list((export/'Assets/RoR2').rglob(name+'.asset'))
        if len(candidates)!=1:
            raise RuntimeError('Objective item definition ambiguous: '+name)
        roots['item'+name] = candidates[0]
    artifact_keys=[]
    for config in sorted(roots['lunarTeleporterAsset'].parent.glob('EntityStates.LunarTeleporter.*.asset')):
        key='config'+str(len(configs));roots[key]=config;configs.append(key)
    if not any(roots[k].name=='EntityStates.LunarTeleporter.IdleToActive.asset' for k in configs):
        raise RuntimeError('Original primordial teleporter configuration missing')
    for src in sorted(set((export/'Assets/RoR2').glob('**/Artifacts/**/*.asset'))):
        if 'm_Script: {fileID: 1032072274, guid: 951ce57ad999ac1f040a4dceb5f8b763, type: 3}' not in src.read_text(errors='replace'): continue
        key='artifact'+str(len(artifact_keys));roots[key]=src;artifact_keys.append(key)
    if not artifact_keys or not any(roots[k].name=='Devotion.asset' for k in artifact_keys) or not any(roots[k].name=='Prestige.asset' for k in artifact_keys):
        raise RuntimeError('Original objective artifact catalog incomplete')
    pending=list(roots.values()); seen=set(); rows=[]; paths={}; unrequested=[]
    remaps={x['from']:x['to'] for x in previous.get('ui_remaps',[])}
    # J233: the original teleporter's GridLayoutGroup adds one UI type beyond the
    # accepted loading/pickup subset. Use the pinned package's serialized identity.
    grid_meta=WORK/'lab-project/Library/PackageCache/com.unity.ugui@1.0.0/Runtime/UI/Core/Layout/GridLayoutGroup.cs.meta'
    grid_guid=re.search(r'^guid: ([a-f0-9]{32})',grid_meta.read_text(),re.M)[1]
    grid_old='{fileID: -2095666955, guid: d3e719b59ab71ba3f6b398058c866280, type: 3}'
    remaps[grid_old]='{fileID: 11500000, guid: '+grid_guid+', type: 3}'
    ui_edits=[]
    while pending:
        src=pending.pop()
        if src in seen: continue
        seen.add(src)
        if not src.exists(): raise RuntimeError('Objective source missing: '+src.name)
        guid=re.search(r'^guid: ([a-f0-9]{32})',Path(str(src)+'.meta').read_text(),re.M)[1]
        if src.suffix=='.dll':
            if src.name=='UnityEngine.UI.dll' and remaps: continue
            if guid not in existing: raise RuntimeError('Unprovided objective assembly: '+src.name)
            continue
        if src.suffix=='.unity': raise RuntimeError('Objective closure unexpectedly imports a full scene')
        dst=existing.get(guid,stage/'ObjectiveClosure'/src.relative_to(export/'Assets'))
        if guid not in existing:
            dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst);shutil.copy2(Path(str(src)+'.meta'),Path(str(dst)+'.meta'))
        for key,value in roots.items():
            if value==src: paths[key]=str(dst.relative_to(WORK/'lab-project')).lower()
        rows.append({'source':str(src.relative_to(export)),'source_sha256':sha(src),'staged':str(dst.relative_to(WORK/'lab-project')),'bytes':src.stat().st_size,'reused':guid in existing})
        if src.read_bytes()[:5]!=b'%YAML': continue
        original=src.read_text(); generated=original
        if src in [roots[x+k] for x in actors for k in ['Body','Master']]+[roots['teleporterAsset'],roots['lunarTeleporterAsset']]:
            root_id=re.search(r'^--- !u!1 &(-?\d+)',original,re.M)[1]
            generated=re.sub(r'(^--- !u!1 &'+root_id+r'\n.*?)(?=^--- !u!|\Z)',lambda m:re.sub(r'  m_IsActive: [01]','  m_IsActive: 0',m[0]),generated,flags=re.M|re.S)
        if guid in existing: generated=dst.read_text()
        for old,new in remaps.items():
            count=generated.count(old)
            if count: ui_edits.append({'path':str(src.relative_to(export)),'from':old,'to':new,'count':count})
            generated=generated.replace(old,new)
        dst.write_text(generated)
        for dep in {g for _,g,_ in REFERENCE.findall(original) if g and not g.startswith('0000000000000000')}:
            if dep not in index: raise RuntimeError('Unresolved objective reference '+src.name+': '+dep)
            pending.append(index[dep])
        # Deferred model addresses are not a reason to copy Windows bundles. Concrete default
        # avatar/controller/material roots above are selected by original typed/subobject identity.
        for key in re.findall(r'm_AssetGUID: ([a-f0-9]{32})',original):
            unrequested.append({'source':str(src.relative_to(export)),'key':key})
    recipe=read(WORK/'scene-probe-build.json')
    recipe['prefabAssets']=list(dict.fromkeys(recipe['prefabAssets']+[v for k,v in paths.items() if k not in set(support_roots)|{'teleporterIndicatorAsset','objectiveTMPSettingsAsset'}]))
    recipe['objectiveSupportAssets']=[next(x['staged'] for x in rows if x['source']==str(roots[k].relative_to(export))) for k in support_roots]
    recipe['objectiveTMPSettings']=next(x['staged'] for x in rows if x['source']==str(roots['objectiveTMPSettingsAsset'].relative_to(export)))
    recipe['teleporterIndicator']=next(x['staged'] for x in rows if x['source']==str(roots['teleporterIndicatorAsset'].relative_to(export)))
    metadata=read(out/'run-metadata-closure.json')
    scene_roots=[x['staged'] for x in metadata['closure'] if x['source'].endswith('.asset') and re.search(r'^  sceneType: ',(export/x['source']).read_text(errors='replace'),re.M)]
    scenes=[x.lower() for x in scene_roots]
    recipe['prefabAssets']=list({x.casefold():x for x in recipe['prefabAssets']+scene_roots}.values())
    write(WORK/'scene-probe-build.json',recipe)
    actor_specs=[dict(name=x,**{k[0].lower()+k[1:]:paths[x+k] for k in ['Body','Master','Card','Avatar','Controller','Material','Mesh']}) for x in actors]
    write(out/'objective-content.json',{'roots':paths,'closure':rows,'bytes':sum(x['bytes'] for x in rows),'ui_remaps':ui_edits,'query_sha256':sha(query_path),'catalog_sha256':sha(export/'Assets/StreamingAssets/aa/catalog.json'),'deferred_unrequested':unrequested,'prior_art':'R2API.Director f539511e separates director activity, catalog readiness and source DCCS selection; current original TeleporterInteraction/BossGroup/HoldoutZoneController/Queen states govern composition. No source implementation copied.'})
    return dict(run_settings,objectiveWardVisualAssets=[paths['ward'+k] for k in ['Controller','Avatar','Mesh','Material','SphereMaterial']],objectiveSupportAssets=[paths[k] for k in support_roots],objectiveSupportKeys=support_keys,objectiveSupportPaths=support_paths,objectiveWardBuffAsset=paths['objectiveWardBuffAsset'],objectiveTMPSettingsAsset=paths['objectiveTMPSettingsAsset'],objectiveTMPSettingsKey='3f5b5dff67a942289a9defa416b206f3',objectiveStunAsset=paths['objectiveStunAsset'],teleporterLoop=True,teleporterAsset=paths['teleporterAsset'],lunarTeleporterAsset=paths['lunarTeleporterAsset'],teleporterIndicatorAsset=paths['teleporterIndicatorAsset'],teleporterIndicatorKey='ff2b34b72be1ef444a3dcc24d5c10b47',objectiveActors=actor_specs,objectiveConfigAssets=[paths[k] for k in configs],objectiveItemNames=item_names,objectiveItemAssets=[paths['item'+n] for n in item_names],objectiveArtifactAssets=[paths[k] for k in artifact_keys],runSceneDefAssets=scenes)


def sanitize_optional_content(stage,out):
    """Remove unavailable native audio/deferred decals from generated Android prefabs.

    These files are owned ignored copies; script GUID identity is checked against the
    exact preserved Wwise MonoBehaviour assembly, never inferred from a component name.
    """
    meta=stage/'Plugins/AK.Wwise.Unity.MonoBehaviour.dll.meta'
    audio_guid=re.search(r'^guid: ([a-f0-9]{32})',meta.read_text(),re.M)[1]
    if audio_guid!='2b6c926553287666f24ffd5af5ba21cb':raise RuntimeError('Wwise component identity drift')
    decal_guid=re.search(r'^guid: ([a-f0-9]{32})',(stage/'Plugins/Decalicious.dll.meta').read_text(),re.M)[1]
    if decal_guid!='90eda32cd325c26600dacf144354b407':raise RuntimeError('Decalicious component identity drift')
    # J243: measured MonoScript metadata and actual OnEnable/OnWillRenderObject
    # require unavailable deferred shader programs. Keep gameplay/effect lifetime.
    decal_script='m_Script: {fileID: -1252323107, guid: '+decal_guid+', type: 3}'
    changes=[];effects=[]
    effect_script='m_Script: {fileID: 511512695, guid: 951ce57ad999ac1f040a4dceb5f8b763, type: 3}'
    alpha_script='m_Script: {fileID: -2051541306, guid: 951ce57ad999ac1f040a4dceb5f8b763, type: 3}'
    projectile_script='m_Script: {fileID: -1848696948, guid: 951ce57ad999ac1f040a4dceb5f8b763, type: 3}'
    silent_guid=re.search(r'^guid: ([a-f0-9]{32})',(stage/'SilentProjectileBoundary.cs.meta').read_text(),re.M)[1]
    silent_script='m_Script: {fileID: 11500000, guid: '+silent_guid+', type: 3}'
    for src in sorted(stage.rglob('*')):
        if src.suffix not in {'.prefab','.asset'}:continue
        text=src.read_text(errors='replace')
        if not text.startswith('%YAML'):continue
        before=sha(src);removed=set();native_removed=set();decal_removed=set();empty_renderers=[];silent_projectiles=[];generated=text
        if src.suffix=='.prefab':
            if effect_script in text:effects.append(str(src.relative_to(WORK/'lab-project')).lower())
            blocks=re.split(r'(?=^--- !u!)',text,flags=re.M)
            kept=[]
            for block in blocks:
                match=re.match(r'--- !u!114 &(-?\d+)',block)
                if match and re.search(r'm_Script: \{fileID: -?\d+, guid: '+audio_guid+r', type: 3\}',block):native_removed.add(match[1]);removed.add(match[1]);continue
                if match and decal_script in block:decal_removed.add(match[1]);removed.add(match[1]);continue
                kept.append(block)
            if removed:
                generated=''.join(kept)
                generated=re.sub(r'^  - component: \{fileID: (-?\d+)\}\n',lambda m:'' if m[1] in removed else m[0],generated,flags=re.M)
                generated=re.sub(r'\{fileID: (-?\d+)\}',lambda m:'{fileID: 0}' if m[1] in removed else m[0],generated)
            # J245: retain alpha timers/pool completion when their optional decal is
            # absent. Original Initialise still obtains a real, empty Renderer array.
            blocks=re.split(r'(?=^--- !u!)',generated,flags=re.M)
            renderer_objects=set()
            for block in blocks:
                match=re.match(r'--- !u!(\d+) &(-?\d+)',block)
                if match and int(match[1]) in {23,96,120,137,199,212,222}:
                    renderer_objects.add(re.search(r'm_GameObject: \{fileID: (-?\d+)\}',block)[1])
            alpha_objects={re.search(r'm_GameObject: \{fileID: (-?\d+)\}',block)[1] for block in blocks if alpha_script in block and '  decal: {fileID: 0}' in block}
            all_ids={m[1] for m in re.finditer(r'^--- !u!\d+ &(-?\d+)',generated,re.M)}
            for object_id in sorted(alpha_objects-renderer_objects):
                component_id=str(7000000000000000+int(hashlib.sha256((str(src.relative_to(stage))+'|'+object_id).encode()).hexdigest()[:12],16))
                while component_id in all_ids:component_id=str(int(component_id)+1)
                all_ids.add(component_id)
                pattern=r'(^--- !u!1 &'+object_id+r'\n.*?)(?=^--- !u!|\Z)'
                def attach(match):
                    if '  m_Component:\n' not in match[0]:raise RuntimeError('Alpha renderer host component list missing')
                    return match[0].replace('  m_Component:\n','  m_Component:\n  - component: {fileID: '+component_id+'}\n',1)
                generated,count=re.subn(pattern,attach,generated,flags=re.M|re.S)
                if count!=1:raise RuntimeError('Alpha renderer host identity ambiguous')
                generated+='--- !u!23 &'+component_id+'\nMeshRenderer:\n  m_ObjectHideFlags: 0\n  m_CorrespondingSourceObject: {fileID: 0}\n  m_PrefabInstance: {fileID: 0}\n  m_PrefabAsset: {fileID: 0}\n  m_GameObject: {fileID: '+object_id+'}\n  m_Enabled: 0\n  m_CastShadows: 0\n  m_ReceiveShadows: 0\n  m_Materials: []\n'
                empty_renderers.append(object_id)
            # J246: original child-projectile factories bypass the state-config clone.
            # The same measured no-event Awake boundary must travel with those prefabs.
            blocks=re.split(r'(?=^--- !u!)',generated,flags=re.M)
            hosts={re.search(r'm_GameObject: \{fileID: (-?\d+)\}',b)[1] for b in blocks if projectile_script in b}
            prepared={re.search(r'm_GameObject: \{fileID: (-?\d+)\}',b)[1] for b in blocks if silent_script in b}
            for object_id in sorted(hosts-prepared):
                component_id=str(8000000000000000+int(hashlib.sha256((str(src.relative_to(stage))+'|silent|'+object_id).encode()).hexdigest()[:12],16))
                while component_id in all_ids:component_id=str(int(component_id)+1)
                all_ids.add(component_id)
                pattern=r'(^--- !u!1 &'+object_id+r'\n.*?)(?=^--- !u!|\Z)'
                def attach_silent(match):
                    if '  m_Component:\n' not in match[0]:raise RuntimeError('Projectile host component list missing')
                    return match[0].replace('  m_Component:\n','  m_Component:\n  - component: {fileID: '+component_id+'}\n',1)
                generated,count=re.subn(pattern,attach_silent,generated,flags=re.M|re.S)
                if count!=1:raise RuntimeError('Projectile host identity ambiguous')
                generated+='--- !u!114 &'+component_id+'\nMonoBehaviour:\n  m_ObjectHideFlags: 0\n  m_CorrespondingSourceObject: {fileID: 0}\n  m_PrefabInstance: {fileID: 0}\n  m_PrefabAsset: {fileID: 0}\n  m_GameObject: {fileID: '+object_id+'}\n  m_Enabled: 1\n  m_EditorHideFlags: 0\n  '+silent_script+'\n  m_Name:\n  m_EditorClassIdentifier:\n'
                silent_projectiles.append(object_id)
        surface=all(x in text for x in ['  impactEffectPrefab:','  footstepEffectPrefab:','  isSlippery:','  impactSoundString:'])
        if surface:
            generated=re.sub(r'^(  (?:impactEffectPrefab|footstepEffectPrefab):).*$',r'\1 {fileID: 0}',generated,flags=re.M)
            generated=re.sub(r'^(  (?:impactSoundString|materialSwitchString):).*$',r'\1',generated,flags=re.M)
        if generated!=text:
            src.write_text(generated);changes.append(dict(path=str(src.relative_to(WORK/'lab-project')),before_sha256=before,after_sha256=sha(src),removed_native_components=len(native_removed),removed_deferred_decals=len(decal_removed),empty_alpha_renderers=empty_renderers,silent_projectiles=silent_projectiles,silent_surface=surface))
    recipe=read(WORK/'scene-probe-build.json')
    separate={recipe[k].casefold() for k in ['teleportMaterial','barrierEffect','playerDeathEffect','pickupDroplet','genericPickup','teleporterIndicator','objectiveTMPSettings'] if recipe.get(k)}
    separate.update(x.casefold() for x in recipe.get('enemyRewardAssets',[])+recipe.get('objectiveSupportAssets',[]))
    effects=[x for x in effects if x.casefold() not in separate]
    recipe['prefabAssets']=list({x.casefold():x for x in recipe['prefabAssets']+effects}.values());write(WORK/'scene-probe-build.json',recipe)
    write(out/'optional-content-transformation.json',dict(changes=changes,effect_roots=effects,scope='Unavailable native audio, deferred decal and optional impact/footstep presentation only; original surface gameplay properties and remaining component identities retained. Exact source input untouched.',prior_art='Pinned R2API.ContentManagement f539511e registers original EffectDefs; original Decalicious metadata and Nova shader failure govern this generated presentation omission. No community or game implementation copied.'))
    return dict(objectiveEffectAssets=effects)
