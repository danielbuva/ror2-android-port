"""Small loadingbasic import experiment; game startup is a separate gate."""
from common import *
import re, shutil

def scene_prepare():
    from build import preflight
    preflight()
    prior=ROOT/read(WORK/'experiments/scene-closure/latest.json')['path']
    closure=read(prior/'loadingbasic.json'); identities=read(prior/'editor-identities.json')['rows']
    export=ROOT/read(WORK/'config/reconstruction.json')['projects'][0]
    project=WORK/'lab-project';stage=project/'Assets/LabLoadingScene'
    if stage.exists():raise RuntimeError('Previous scene stage exists; preserve and classify it first')
    out=WORK/'experiments/scene-runtime'/now();out.mkdir(parents=True);stage.mkdir()
    mapping={};queries=[]
    for row in identities:
        if row['path']!='Assets/Plugins/UnityEngine.UI.dll':continue
        if not any(e['target']==row['path'] and e['fileID']==row['fileID'] for e in closure['script_references']):continue
        name=row['scriptType'].split('.')[-1]
        candidates=list((project/'Library/PackageCache/com.unity.ugui@1.0.0').rglob(name+'.cs'))
        if len(candidates)!=1:raise RuntimeError('Ambiguous package UI script '+name)
        src=candidates[0];guid=re.search(r'^guid: ([a-f0-9]{32})',Path(str(src)+'.meta').read_text(),re.M).group(1)
        old='{fileID: '+row['fileID']+', guid: d3e719b59ab71ba3f6b398058c866280, type: 3}'
        mapping[old]='{fileID: 11500000, guid: '+guid+', type: 3}'
        queries.append({'path':'Packages/com.unity.ugui/'+str(src.relative_to(project/'Library/PackageCache/com.unity.ugui@1.0.0')),'fileID':'11500000'})
    copied={};edits=[]
    for relative in closure['files']:
        src=export/relative
        if src.suffix=='.dll':continue
        dst=stage/Path(relative).relative_to('Assets');dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(src,dst);shutil.copy2(Path(str(src)+'.meta'),Path(str(dst)+'.meta'));copied[relative]=sha(src)
        if src.read_bytes()[:5]==b'%YAML':
            text=src.read_text()
            for old,new in mapping.items():
                count=text.count(old)
                if count:edits.append({'path':relative,'from':old,'to':new,'count':count});text=text.replace(old,new)
            dst.write_text(text)
    original=read(WORK/'experiments/original-closure-runtime/20260913T024051.910924Z/slice-provenance.json')['original_assemblies']
    for name,h in original.items():
        src=game()/'Risk of Rain 2_Data/Managed'/name
        if sha(src)!=h:raise RuntimeError('Original assembly drift '+name)
        dst=stage/'Plugins'/name;dst.parent.mkdir(exist_ok=True)
        shutil.copy2(src,dst);shutil.copy2(export/'Assets/Plugins'/(name+'.meta'),Path(str(dst)+'.meta'))
    (stage/'link.xml').write_text('<linker><assembly fullname="RoR2" preserve="all" /></linker>\n')
    result={'attempt':out.name,'stage':str(stage),'scene':'Assets/LabLoadingScene/'+str(Path(closure['root']).relative_to('Assets')),'copied_source_hashes':copied,'original_assemblies':original,'ui_remaps':edits,'status':'staged; import and identity assertions required before any scene execution','evidence':str(out.relative_to(ROOT))}
    write(out/'attempt.json',result);write(out.parent/'current.json',{'path':str(out.relative_to(ROOT))})
    write(project/'Assets/LabReferenceQuery.json',{'attempt':out.name,'output':str(out/'ui-identities.json'),'queries':queries})
    shutil.copy2(ROOT/'tools/unity/ReferenceIdentityProbe.cs',project/'Assets/Editor/ReferenceIdentityProbe.cs')
    print(json.dumps({'evidence':result['evidence'],'ui_reference_edits':sum(e['count'] for e in edits),'status':result['status']},indent=2))

def scene_run():
    from device import Device, PACKAGE
    from build import preflight
    import time
    preflight();out=ROOT/read(WORK/'experiments/scene-runtime/current.json')['path'];attempt=read(out/'attempt.json')
    if (out/'runtime-result.json').exists():raise RuntimeError('Attempt already terminal; preserve before retry')
    built=read(WORK/'config/current-build.json')
    if not built.get('success') or 'loadingbasic-lab' not in built.get('payload',{}):raise RuntimeError('No attributed scene payload build')
    stage=Path(attempt['stage'])
    for name,h in attempt['original_assemblies'].items():
        if sha(stage/'Plugins'/name)!=h:raise RuntimeError('Original assembly changed '+name)
    result={'success':False,'attempt':out.name,'build':built,'scope':'Isolated original loadingbasic content with application startup inactive'}
    d=Device();had=d.exists()
    try:
        result['install']=d.install(built['apk']);d.launch();result['sync']=d.sync();result['launch']=d.launch();pid=result['launch']['pid'];start=time.monotonic()
        while time.monotonic()-start<35:
            if d.sh('pidof',PACKAGE,check=False).strip()!=pid:raise RuntimeError('Scene process died or changed')
            time.sleep(1)
        path=read(WORK/'device/runtime.json')['persistentDataPath'];report=json.loads(d.sh('cat',path+'/loading-scene-probe.json'));write(out/'device-probe.json',report)
        result['success']=report['success'] and report['attempt']==out.name and str(report['pid'])==pid;result['survival_seconds']=time.monotonic()-start
        d.collect('all',out/'device')
    except Exception as e:
        result['error']=str(e)
        if 'install' in result:
            try:d.collect('all',out/'device')
            except Exception as capture:result['capture_error']=str(capture)
    finally:
        if not had and (WORK/'device/installed.json').exists():
            try:result['cleanup']=d.reset()
            except Exception as e:result['cleanup_error']=str(e);result['success']=False
        write(out/'runtime-result.json',result)
    print(json.dumps({'success':result['success'],'evidence':str(out.relative_to(ROOT)),'error':result.get('error')},indent=2))
    if not result['success']:raise RuntimeError('Scene probe failed; inspect '+str(out))

def scene_arm():
    """After UI identity validation, isolate startup for the content-only probe."""
    from build import preflight
    preflight();out=ROOT/read(WORK/'experiments/scene-runtime/current.json')['path'];r=read(out/'attempt.json')
    if 'isolation' in r:raise RuntimeError('Scene already armed; do not apply the transformation twice')
    ui=read(out/'ui-identities.json')
    if len(ui['rows'])!=4 or not all(x['resolved'] and x['scriptType'].startswith('UnityEngine.UI.') for x in ui['rows']):raise RuntimeError('Required UI script identity assertions failed')
    identities=read(ROOT/read(WORK/'experiments/scene-closure/latest.json')['path']/'editor-identities.json')['rows']
    script=next(x for x in identities if x['scriptType']=='RoR2.RoR2Application')
    path=WORK/'lab-project'/r['scene'];blocks=re.split(r'(?=^--- !u!)',path.read_text(),flags=re.M)
    components=[b for b in blocks if 'm_Script: {fileID: '+script['fileID']+', guid: 951ce57ad999ac1f040a4dceb5f8b763,' in b]
    if len(components)!=1:raise RuntimeError('Expected exactly one original application component')
    object_id=re.search(r'm_GameObject: \{fileID: (\d+)\}',components[0])[1]
    indexes=[i for i,b in enumerate(blocks) if re.match(r'--- !u!1 &'+object_id+r'\n',b)]
    if len(indexes)!=1:raise RuntimeError('Application GameObject identity mismatch')
    i=indexes[0]
    if 'm_Name: RoR2Application\n' not in blocks[i] or 'm_IsActive: 1' not in blocks[i]:raise RuntimeError('Unexpected application object state')
    blocks[i]=blocks[i].replace('m_IsActive: 1','m_IsActive: 0');path.write_text(''.join(blocks))
    r['isolation']={'gameObjectFileID':int(object_id),'name':'RoR2Application','m_IsActive':0,'reason':'Content-only scene probe; startup and entitlement/authentication logic unchanged and unexecuted'};write(out/'attempt.json',r)
    write(WORK/'scene-probe-build.json',{'scene':r['scene']})
    resources=Path(r['stage'])/'Resources';resources.mkdir()
    write(resources/'LoadingSceneProbe.json',{'attempt':out.name,'bundle':'loadingbasic-lab','scene':r['scene']})
    shutil.copy2(ROOT/'tools/unity/LoadingSceneProbe.cs',Path(r['stage'])/'LoadingSceneProbe.cs')
    print(json.dumps({'armed':True,'evidence':str(out.relative_to(ROOT)),'scope':r['isolation']['reason']}))
