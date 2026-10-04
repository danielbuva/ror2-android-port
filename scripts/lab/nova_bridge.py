"""Two bounded sequential probes: Unity physical exposure, then original spawned Commando."""
from common import *
import re

RAW='nova-unity-raw'
BODY='body-state-spawn-state-auto-nova-controls'

def insert_axes(before,axes):
    marker='  m_UsePhysicalKeys:'
    if before.count(marker)!=1:raise RuntimeError('InputManager terminal property changed; review before staging')
    index=before.index(marker)
    return before[:index]+axes+before[index:]

def prepare():
    active=WORK/'lab-project/Assets/LabLoadingScene'
    if (active/'Resources/MovementBatchProbe.json').exists() and read(active/'Resources/MovementBatchProbe.json').get('primaryFireConfigAsset'):
        return prepare_spine()
    from scene_runtime import body_start_loadout_prepare
    body_start_loadout_prepare(spawn_states=True,teleport_material=True,nova_input=True,cases=[RAW])
    out=ROOT/read(WORK/'experiments/scene-runtime/current.json')['path'];a=read(out/'attempt.json');stage=Path(a['stage'])
    cfg=read(stage/'Resources/MovementBatchProbe.json');cfg['displayAssets']=[x.lower() for x in read(WORK/'scene-probe-build.json')['prefabAssets'][:6]];write(stage/'Resources/MovementBatchProbe.json',cfg)
    settings=WORK/'lab-project/ProjectSettings/InputManager.asset';before=settings.read_text()
    if 'm_Name: NovaLabAxis' in before:raise RuntimeError('Existing Nova axes must be reviewed/restored first')
    (out/'InputManager-before.asset').write_text(before)
    axes=''
    for i in range(16):
        axes+=f'''  - serializedVersion: 3
    m_Name: NovaLabAxis{i}
    descriptiveName:
    descriptiveNegativeName:
    negativeButton:
    positiveButton:
    altNegativeButton:
    altPositiveButton:
    gravity: 0
    dead: 0
    sensitivity: 1
    snap: 0
    invert: 0
    type: 2
    axis: {i}
    joyNum: 1
'''
    settings.write_text(insert_axes(before,axes))
    request=stage/'Editor/character-motor-order.json';order=read(request);order['novaInputOrder']=-20000;write(request,order)
    a.update({'nova_input_bridge':True,'batch_seconds':{RAW:140,BODY:120}});write(out/'attempt.json',a)
    write(out/'nova-contract.json',{'input_manager_before_sha256':sha(out/'InputManager-before.asset'),'input_manager_after_sha256':sha(settings),'scope':'Nova only; original InputBankTest producer; no movement/state/motor/skill rewrites; no Rewired replacement','prior_art':'Starstorm2 a9a4badd BorgMain consumes inputBank and retains GenericCharacterMain base ProcessJump/FixedUpdate; no Android backend provided','catalog':'Measured JumpBoost/JumpDamageStrike plus GummyCloneIdentifier in original empty inventory; explicit new combined subset, old cases unchanged','mapping':'Measure Unity slot-1 axes/buttons, then push attempt-bound JSON; skills disabled in movement proof','visual':'Recovered transform/renderer-only model display follows original ModelLocator; fixed bind pose, diagnostic floor/camera/aim stance'})

def prepare_spine():
    """Continue the accepted active stage; use the measured mapping without repeating its capture."""
    import shutil
    from build import preflight
    preflight();parent=ROOT/read(WORK/'experiments/scene-runtime/current.json')['path'];a=read(parent/'attempt.json');stage=Path(a['stage'])
    checkpoint=read(WORK/'checkpoints/LAST_KNOWN_GOOD_NOVA_INPUT_BRIDGE.json');mapping=dict(checkpoint['mapping'])
    if checkpoint['input_id']!=read(WORK/'inventory/files.json')['input_id'] or sha(ROOT/mapping['observation'])!=mapping['observation_sha256']:raise RuntimeError('Accepted input/mapping changed')
    for name,h in checkpoint['original_assemblies'].items():
        if sha(stage/'Plugins'/name)!=h:raise RuntimeError('Original spine assembly drift')
    out=WORK/'experiments/scene-runtime'/now();out.mkdir(parents=True)
    write(out/'rollback.json',{'physical':read(WORK/'checkpoints/LAST_KNOWN_GOOD_SPINE_PHYSICAL.json') if (WORK/'checkpoints/LAST_KNOWN_GOOD_SPINE_PHYSICAL.json').exists() else checkpoint,'combat':read(WORK/'checkpoints/LAST_KNOWN_GOOD_COMBAT_SCRIPTED.json') if (WORK/'checkpoints/LAST_KNOWN_GOOD_COMBAT_SCRIPTED.json').exists() else None,'primary':read(WORK/'checkpoints/LAST_KNOWN_GOOD_PRIMARY_ACTIVATION.json'),'before':str(parent.relative_to(ROOT)),'build':read(WORK/'config/current-build.json')})
    shutil.copy2(ROOT/checkpoint['evidence']/'original-motor-order.json',out/'original-motor-order.json')
    for name in ['MovementBatchProbe','PrimaryFireBoundary','CombatSpineBoundary','SilentProjectileBoundary','SpawnStateBoundary','AutomaticSpawnBoundary','AutomaticModelBoundary','NovaInputBoundary','NovaInputBridge','NovaDiagnosticDisplay']:shutil.copy2(ROOT/'tools/unity'/(name+'.cs'),stage/(name+'.cs'))
    cfg=read(stage/'Resources/MovementBatchProbe.json');cfg.update(stage_combat_configs(stage,a,out));cfg.update({'attempt':out.name,'combatSpine':True,'launchPlayableSlice':True});write(stage/'Resources/MovementBatchProbe.json',cfg)
    spine='body-state-spawn-state-auto-nova-spine'
    a.update({'attempt':out.name,'playable_spine':True,'nova_input_bridge':True,'parent':str(parent.relative_to(ROOT)),'batch_ids':[spine+'-bringup'],'batch_seconds':{spine+'-bringup':55,spine:120}});write(out/'attempt.json',a)
    mapping['accepted_mapping_attempt']=mapping['attempt'];mapping['attempt']=out.name;write(out/'nova-input-mapping.json',mapping)
    write(WORK/'experiments/scene-runtime/current.json',{'path':str(out.relative_to(ROOT))});print(json.dumps({'attempt':str(out.relative_to(ROOT)),'spine':True}))

def stage_combat_configs(stage,previous,out):
    """Existing YAML closure traversal for the three default Commando state configurations."""
    import shutil
    export=ROOT/read(WORK/'config/reconstruction.json')['projects'][0];index={};existing={}
    for base,target in [(export/'Assets',index),(stage,existing)]:
        for meta in base.rglob('*.meta'):
            match=re.search(r'^guid: ([a-f0-9]{32})',meta.read_text(errors='replace'),re.M)
            if match:target[match[1]]=Path(str(meta)[:-5])
    skills=export/'Assets/RoR2/Base/Characters/Commando/Skills'
    roots={'secondaryConfigAsset':skills/'EntityStates.Commando.CommandoWeapon.FireFMJ.asset','utilityConfigAsset':skills/'EntityStates.Commando.DodgeState.asset','specialConfigAsset':export/'Assets/RoR2/Junk/Characters/CommandoPerformanceTest/EntityStates.Commando.CommandoWeapon.FireBarrage.asset'}
    pending=list(roots.values());seen=set();paths={};rows=[];remaps={r['from']:r['to'] for r in previous.get('ui_remaps',[])}
    while pending:
        src=pending.pop()
        if src in seen:continue
        seen.add(src);meta=Path(str(src)+'.meta');guid=re.search(r'^guid: ([a-f0-9]{32})',meta.read_text(),re.M)[1]
        if src.suffix=='.dll':
            if src.name=='UnityEngine.UI.dll' and remaps:continue
            if guid not in existing:raise RuntimeError('Unprovided combat assembly '+src.name)
            continue
        dst=existing.get(guid,stage/'CombatClosure'/src.relative_to(export/'Assets'))
        if guid not in existing:
            dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst);shutil.copy2(meta,Path(str(dst)+'.meta'))
        rows.append({'source':str(src.relative_to(export)),'source_sha256':sha(src),'staged':str(dst.relative_to(WORK/'lab-project')),'reused':guid in existing})
        for key,value in roots.items():
            if src==value:paths[key]=str(dst.relative_to(WORK/'lab-project'))
        if src.read_bytes()[:5]==b'%YAML':
            if guid not in existing:
                text=dst.read_text()
                for old,new in remaps.items():text=text.replace(old,new)
                dst.write_text(text)
            for dep in set(re.findall(r'guid: ([a-f0-9]{32})',src.read_text())):
                if dep.startswith('0000000000000000'):continue
                if dep not in index:raise RuntimeError('Unresolved combat GUID')
                pending.append(index[dep])
    recipe=read(WORK/'scene-probe-build.json');recipe['prefabAssets']=list(dict.fromkeys(recipe['prefabAssets']+list(paths.values())));write(WORK/'scene-probe-build.json',recipe)
    write(out/'combat-contract.json',{'scope':'Integrated default FMJ/roll/barrage and original BulletAttack/HealthComponent target; explicit silent effects-excluded owned copies','prior_art':'Pinned Starstorm2 a9a4badd Deadeye uses authority-gated original BulletAttack and separate visual effects; BorgMain retains original inputBank/GenericCharacterMain behavior. No community code copied.','special_config':'Only exported configuration for exact FireBarrage targetType; preserve its original parameters despite recovered Junk directory.','closure':rows})
    return {key:value.lower() for key,value in paths.items()}

def run_probe(physical=False,retry=False):
    from scene_runtime import movement_batch_run
    if physical:
        out=ROOT/read(WORK/'experiments/scene-runtime/current.json')['path'];a=read(out/'attempt.json');stage=Path(a['stage'])
        receipt=stage/'Editor/character-motor-order-result.json';order=read(receipt);expected=read(out/'original-motor-order.json')['rows'][0]['order']
        terminal=WORK/'lab-build/result.json'
        if order.get('after')!=expected or order.get('novaAfter')!=-20000 or not terminal.exists() or receipt.stat().st_mtime_ns>terminal.stat().st_mtime_ns:raise RuntimeError('Restore original motor/Nova producer order, then complete forced build before physical simulation')
    selected='body-state-spawn-state-auto-nova-spine' if physical and a.get('playable_spine') else BODY if physical else RAW
    movement_batch_run(cases=[selected],retry=physical or retry,interactive=True)

def bind():
    from device import Device
    out=ROOT/read(WORK/'experiments/scene-runtime/current.json')['path'];a=read(out/'attempt.json')
    mapping=read(WORK/'config/nova-input-mapping.json');source=(ROOT/mapping['observation']).resolve()
    if not source.is_relative_to(out.resolve()) or mapping['attempt']!=a['attempt']:raise RuntimeError('Stale or unrelated Nova mapping source')
    report=read(source);samples=(report.get('nova') or {}).get('observations',[])
    if not report.get('success') or report.get('phase')!='complete' or report.get('id')!=RAW or report.get('attempt')!=a['attempt']:raise RuntimeError('Incomplete/current-attempt Unity exposure required')
    axes=[mapping[key] for key in ['moveX','moveY','aimX','aimY']];buttons=[mapping[key] for key in ['jump','primary','secondary','utility','special']]
    if len(set(axes))!=4 or any(not isinstance(i,int) or not 0<=i<16 for i in axes) or len(set(buttons))!=5 or any(not isinstance(i,int) or not 0<=i<20 for i in buttons):raise RuntimeError('Invalid Nova bindings')
    if mapping.get('enableSkills') or mapping['moveYSign'] not in [-1,1] or mapping['aimYSign'] not in [-1,1]:raise RuntimeError('Movement-only mapping/sign contract changed')
    for axis in axes:
        values=[s['raw']['axes'][axis] for s in samples]
        if min(values)>-.7 or max(values)<.7:raise RuntimeError('Mapped stick axis lacks bidirectional physical evidence')
    for button in buttons:
        if not any(s['raw']['buttons'][button] for s in samples):raise RuntimeError('Mapped button lacks physical evidence')
    mapping['observation_sha256']=sha(source);target=out/'nova-input-mapping.json';write(target,mapping)
    d=Device();d.owned();runtime=read(WORK/'device/runtime.json')['persistentDataPath']
    expected='/storage/emulated/0/Android/data/dev.ror2lab.arm64/files'
    if runtime!=expected:raise RuntimeError('Unexpected lab runtime mapping destination')
    d.cmd('push',str(target),runtime+'/nova-input-mapping.json');print(json.dumps({'mapping':str(target.relative_to(ROOT)),'source_sha256':mapping['observation_sha256']}))

def current_errors(text,pid):
    """The existing lab deliberately rejects one Windows shader bundle; reject other errors."""
    lines=[line for line in text.splitlines() if re.search(r'\s'+re.escape(str(pid))+r'\s',line)]
    known=["The file can not be loaded because it was created for another build target", "Please make sure to build AssetBundles using the build target", "File's Build target is: 19", "The AssetBundle 'windows-shaders.bundle' can't be loaded"]
    failures=[]
    for i,line in enumerate(lines):
        if not re.search(r'\sE\s+(Unity|AndroidRuntime)\s*:',line):continue
        if any(message in line for message in known):continue
        if "Unknown error occurred while loading 'archive:" in line and i>0 and "File's Build target is: 19" in lines[i-1] and i+1<len(lines) and "The AssetBundle 'windows-shaders.bundle'" in lines[i+1]:continue
        failures.append(line)
    return failures
