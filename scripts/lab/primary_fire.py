"""Two independent original-primary probes cloned from the accepted Nova stage."""
from common import *
import re,shutil

PREFIX='body-state-spawn-state-primary-'
CASES=[PREFIX+'contract',PREFIX+'native']

def prepare():
    checkpoint=read(WORK/'checkpoints/LAST_KNOWN_GOOD_NOVA_INPUT_BRIDGE.json')
    parent=ROOT/read(WORK/'experiments/scene-runtime/current.json')['path']
    previous=read(parent/'attempt.json');stage=Path(previous['stage'])
    if not previous.get('nova_input_bridge') or not stage.is_dir():raise RuntimeError('Primary probe requires the accepted active Nova stage')
    for name,h in previous['original_assemblies'].items():
        if sha(stage/'Plugins'/name)!=h:raise RuntimeError('Original assembly drift before primary staging')
    out=WORK/'experiments/scene-runtime'/now();out.mkdir(parents=True)
    write(out/'rollback.json',{'checkpoint':checkpoint,'parent':str(parent.relative_to(ROOT)),'build':read(WORK/'config/current-build.json'),'recipe':read(WORK/'scene-probe-build.json'),'config':read(stage/'Resources/MovementBatchProbe.json')})
    export=ROOT/read(WORK/'config/reconstruction.json')['projects'][0]
    index={};existing={}
    for base,target in [(export/'Assets',index),(stage,existing)]:
        for meta in base.rglob('*.meta'):
            match=re.search(r'^guid: ([a-f0-9]{32})',meta.read_text(errors='replace'),re.M)
            if match:target[match[1]]=Path(str(meta)[:-5])
    commando=export/'Assets/RoR2/Base/Characters/Commando'
    roots={'primaryFireConfigAsset':commando/'EntityStates.Commando.CommandoWeapon.FirePistol2.asset','primaryReloadConfigAsset':commando/'EntityStates.Commando.CommandoWeapon.ReloadPistols.asset','primaryItemAsset':export/'Assets/RoR2/DLC2/Items/IncreasePrimaryDamage/IncreasePrimaryDamage.asset'}
    pending=list(roots.values());seen=set();rows=[];paths={}
    ui_remaps={row['from']:row['to'] for row in previous.get('ui_remaps',[])}
    # Same bounded YAML GUID traversal as landing_batch_prepare; no new provider or runtime loader.
    while pending:
        src=pending.pop()
        if src in seen:continue
        seen.add(src);meta=Path(str(src)+'.meta');guid=re.search(r'^guid: ([a-f0-9]{32})',meta.read_text(),re.M)[1]
        if src.suffix=='.dll':
            if src.name=='UnityEngine.UI.dll' and ui_remaps:continue
            if guid not in existing:raise RuntimeError('Unprovided primary script assembly '+src.name)
            continue
        dst=existing.get(guid,stage/'PrimaryClosure'/src.relative_to(export/'Assets'))
        if guid not in existing:
            dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst);shutil.copy2(meta,Path(str(dst)+'.meta'))
        rows.append({'source':str(src.relative_to(export)),'sha256':sha(src),'staged':str(dst.relative_to(WORK/'lab-project')),'reused':guid in existing})
        for key,value in roots.items():
            if src==value:paths[key]=str(dst.relative_to(WORK/'lab-project'))
        if src.read_bytes()[:5]==b'%YAML':
            if guid not in existing:
                text=dst.read_text()
                for old,new in ui_remaps.items():text=text.replace(old,new)
                if 'guid: d3e719b59ab71ba3f6b398058c866280' in text:raise RuntimeError('Unmeasured primary Unity UI identity')
                dst.write_text(text)
            for dependency in set(re.findall(r'guid: ([a-f0-9]{32})',src.read_text())):
                if dependency.startswith('0000000000000000'):continue
                if dependency not in index:raise RuntimeError('Unresolved primary GUID')
                pending.append(index[dependency])
    cfg=read(stage/'Resources/MovementBatchProbe.json');cfg.update({k:v.lower() for k,v in paths.items()});cfg['attempt']=out.name;write(stage/'Resources/MovementBatchProbe.json',cfg)
    recipe=read(WORK/'scene-probe-build.json');recipe['prefabAssets']+=list(paths.values());recipe['prefabAssets']=list(dict.fromkeys(recipe['prefabAssets']));write(WORK/'scene-probe-build.json',recipe)
    for helper in ['MovementBatchProbe','PrimaryFireBoundary']:shutil.copy2(ROOT/'tools/unity'/(helper+'.cs'),stage/(helper+'.cs'))
    a=dict(previous);a.update({'attempt':out.name,'parent':str(parent.relative_to(ROOT)),'nova_input_bridge':False,'primary_fire':True,'batch_ids':CASES,'batch_seconds':{case:35 for case in CASES}});write(out/'attempt.json',a)
    write(out/'primary-contract.json',{'scope':'Original factory/activation and separately first unmodified native firing failure; no physical skill acceptance','prior_art':'Starstorm2 a9a4badd Deadeye uses authority-gated original BulletAttack Fire and separate tracer/hit effects; R2API Sound preserves native bank/result lifetime','original_source':'RoR2 0497a902a7aaf3c97fa2f1251a5364723b0c1b422839f7002a4b5f9c02563e4f: FirePistol2, SteppedSkillDef, GenericSkill, CharacterBody.OnSkillActivated','closure':rows})
    write(WORK/'experiments/scene-runtime/current.json',{'path':str(out.relative_to(ROOT))})
    print(json.dumps({'attempt':str(out.relative_to(ROOT)),'new_assets':sum(not x['reused'] for x in rows),'cases':CASES}))

def run():
    from scene_runtime import movement_batch_run
    out=ROOT/read(WORK/'experiments/scene-runtime/current.json')['path']
    if not read(out/'attempt.json').get('primary_fire'):raise RuntimeError('Not a primary firing attempt')
    movement_batch_run(cases=[CASES[0]],retry=(out/'batch-result.json').exists(),interactive=True)
    # The second cold launch depends on the first contract; never repeat a failed prerequisite.
    movement_batch_run(cases=[CASES[1]],retry=True,interactive=True)
