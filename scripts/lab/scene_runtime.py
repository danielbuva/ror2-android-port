"""Small loadingbasic import experiment; game startup is a separate gate."""
from common import *
import re, shutil

def scene_prepare(include_prefab=False):
    from build import preflight
    preflight()
    prior=ROOT/read(WORK/'experiments/scene-closure/latest.json')['path']
    closure=read(prior/'loadingbasic.json'); identities=read(prior/'editor-identities.json')['rows']
    prefab=None
    if include_prefab:
        prefab=read(prior/'CommandoBody.json')
        closure['files']=sorted(set(closure['files']+prefab['files']))
        closure['script_references']+=prefab['script_references']
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
    result['ui_query_count']=len(queries)
    if prefab:result['prefab']='Assets/LabLoadingScene/'+str(Path(prefab['root']).relative_to('Assets'))
    write(out/'attempt.json',result);write(out.parent/'current.json',{'path':str(out.relative_to(ROOT))})
    write(project/'Assets/LabReferenceQuery.json',{'attempt':out.name,'output':str(out/'ui-identities.json'),'queries':queries})
    shutil.copy2(ROOT/'tools/unity/ReferenceIdentityProbe.cs',project/'Assets/Editor/ReferenceIdentityProbe.cs')
    print(json.dumps({'evidence':result['evidence'],'ui_reference_edits':sum(e['count'] for e in edits),'status':result['status']},indent=2))

def scene_run(verification=False):
    from device import Device, PACKAGE
    from build import preflight
    import time
    preflight();out=ROOT/read(WORK/'experiments/scene-runtime/current.json')['path'];attempt=read(out/'attempt.json')
    built=read(WORK/'config/current-build.json')
    if verification:
        previous=read(out/'runtime-result.json')
        if not attempt.get('material_render') or not previous['success'] or previous['build']['apk_sha256']!=built['apk_sha256'] or previous['build']['payload']!=built['payload']:raise RuntimeError('Verification requires passing material attempt and same APK/payload')
        parent=out;out=parent/'verification'/now()/parent.name;out.mkdir(parents=True);write(out/'attempt.json',{**attempt,'verification_of':str(parent.relative_to(ROOT))})
    elif (out/'runtime-result.json').exists():raise RuntimeError('Attempt already terminal; preserve before retry')
    if not built.get('success') or 'loadingbasic-lab' not in built.get('payload',{}):raise RuntimeError('No attributed scene payload build')
    stage=Path(attempt['stage'])
    for name,h in attempt['original_assemblies'].items():
        if sha(stage/'Plugins'/name)!=attempt.get('transformed_assemblies',{}).get(name,h):raise RuntimeError('Staged assembly changed '+name)
    result={'success':False,'attempt':out.name,'build':built,'scope':'Original startup first-yield/PreFrame segment and profile filesystem candidate' if attempt.get('startup') else 'Original '+('skin baking' if attempt.get('skin') else 'avatar subobject' if attempt.get('avatar') else 'controller')+' deferred request; startup inactive' if attempt.get('controller') else 'Isolated original loadingbasic content with application startup inactive'}
    d=Device();had=d.exists()
    try:
        result['install']=d.install(built['apk']);d.launch();result['sync']=d.sync();result['launch']=d.launch();pid=result['launch']['pid'];start=time.monotonic()
        while time.monotonic()-start<(50 if attempt.get('startup') else 70 if attempt.get('skin') else 50 if attempt.get('controller') else 35):
            if d.sh('pidof',PACKAGE,check=False).strip()!=pid:raise RuntimeError('Scene process died or changed')
            time.sleep(1)
        path=read(WORK/'device/runtime.json')['persistentDataPath'];report_name='startup-segment-probe.json' if attempt.get('startup') else 'controller-address-probe.json' if attempt.get('controller') else 'loading-scene-probe.json';report=json.loads(d.sh('cat',path+'/'+report_name));write(out/'device-probe.json',report)
        result['success']=report['success'] and report['attempt']==out.name and str(report['pid'])==pid;result['survival_seconds']=time.monotonic()-start
        if not result['success']:result['error']=report.get('error') or 'Probe assertions or attempt/PID attribution failed'
        if attempt.get('controller'):
            d.cmd('pull',path+'/controller-catalog',str(out/'controller-catalog'))
        if attempt.get('material_render'):
            material=json.loads(d.sh('cat',path+'/commando-material-probe.json'));write(out/'material-probe.json',material)
            result['success']=result['success'] and material['success'] and material['attempt']==out.name and str(material['pid'])==pid
            if not material['success']:result['error']=material.get('error') or 'Material assertions failed'
            for name in ['commando-material-control.png','commando-material-albedo.png','commando-material-emission.png']:
                d.cmd('pull',path+'/'+name,str(out/name))
                if not (out/name).read_bytes().startswith(b'\x89PNG\r\n\x1a\n'):raise RuntimeError('Material capture missing or invalid')
        if attempt.get('state_tick'):
            state=json.loads(d.sh('cat',path+'/entity-state-tick-probe.json'));write(out/'state-tick-probe.json',state)
            result['success']=result['success'] and state['success'] and state['attempt']==out.name and str(state['pid'])==pid
            if not result['success']:result['error']=state.get('error') or result.get('error') or 'State tick assertions/attribution failed'
        if attempt.get('pose'):
            pose=json.loads(d.sh('cat',path+'/commando-pose.json'));write(out/'pose-probe.json',pose)
            result['success']=result['success'] and pose['success'] and pose['attempt']==out.name and str(pose['pid'])==pid
            for name in ['commando-pose-A.png','commando-pose-B.png']:
                d.cmd('pull',path+'/'+name,str(out/name))
                if not (out/name).read_bytes().startswith(b'\x89PNG\r\n\x1a\n'):raise RuntimeError('Pose capture missing or invalid')
        foreground=d.sh('dumpsys','activity','activities');write(out/'foreground.json',{'activity_dump':foreground})
        resumed=[line for line in foreground.splitlines() if 'mResumedActivity:' in line or 'topResumedActivity=' in line]
        result['foreground_verified']=bool(resumed) and all(PACKAGE+'/' in line for line in resumed)
        if not result['foreground_verified']:raise RuntimeError('Lab is not the verified foreground activity; screenshot cannot establish visual acceptance')
        d.collect('all',out/'device')
    except Exception as e:
        result['success']=False;result['error']=str(e)
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
    if len(ui['rows'])!=r.get('ui_query_count',4) or not all(x['resolved'] and x['scriptType'].startswith('UnityEngine.UI.') for x in ui['rows']):raise RuntimeError('Required UI script identity assertions failed')
    if r.get('prefab'):
        expected=['UnityEditor.Animations.AnimatorController','UnityEngine.Avatar','UnityEngine.Mesh','UnityEngine.Mesh','UnityEngine.Mesh','UnityEngine.Material']
        if not r.get('default_assets'):raise RuntimeError('Trace and bind default-skin dependencies before arming prefab')
        asset_rows=read(out/'default-asset-identities.json')['rows']
        if len(asset_rows)!=6 or [x['objectType'] for x in asset_rows]!=expected or not all(x['resolved'] for x in asset_rows):raise RuntimeError('Default-skin imported asset identity assertions failed')
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
    if r.get('prefab'):
        prefab_path=WORK/'lab-project'/r['prefab'];text=prefab_path.read_text();parts=re.split(r'(?=^--- !u!)',text,flags=re.M)
        candidates=[i for i,b in enumerate(parts) if b.startswith('--- !u!1 ') and 'm_Name: CommandoBody\n' in b]
        if len(candidates)!=1 or 'm_IsActive: 1' not in parts[candidates[0]]:raise RuntimeError('Unexpected original Commando root')
        parts[candidates[0]]=parts[candidates[0]].replace('m_IsActive: 1','m_IsActive: 0');prefab_path.write_text(''.join(parts))
        r['prefab_isolation']='Original CommandoBody root inactive before instantiation; no Awake/OnEnable or simulation acceptance'
        write(out/'attempt.json',r)
    write(WORK/'scene-probe-build.json',{'scene':r['scene'],'prefab':r.get('prefab',''),'prefabAssets':r.get('default_assets',[])})
    resources=Path(r['stage'])/'Resources';resources.mkdir()
    write(resources/'LoadingSceneProbe.json',{'attempt':out.name,'bundle':'loadingbasic-lab','scene':r['scene'],'prefab':r.get('prefab',''),'prefabAssets':r.get('default_assets',[])})
    shutil.copy2(ROOT/'tools/unity/LoadingSceneProbe.cs',Path(r['stage'])/'LoadingSceneProbe.cs')
    shutil.copy2(ROOT/'tools/unity/CommandoPosePreview.cs',Path(r['stage'])/'CommandoPosePreview.cs')
    print(json.dumps({'armed':True,'evidence':str(out.relative_to(ROOT)),'scope':r['isolation']['reason']}))

def prefab_bind():
    """Stage only measured default-skin content for binding on an inactive clone."""
    from build import preflight
    from collections import deque
    preflight();out=ROOT/read(WORK/'experiments/scene-runtime/current.json')['path'];r=read(out/'attempt.json');stage=Path(r['stage'])
    if not r.get('prefab') or r.get('default_assets'):raise RuntimeError('Expected a fresh prefab staging attempt')
    catalog=read(out/'default-skin-addresses.json')['locations']+read(out/'default-material-address.json')['locations']
    required={'48ef8327759dd43439416d4823124d9c':('UnityEngine.RuntimeAnimatorController','animCommando.controller'),'47f06aa0c19f14749840757bbb39d4c8':('UnityEngine.Avatar','mdlCommandoDualies.fbx'),'529399f7071eb2641897f2895c5d4ef0':('RoR2.SkinDefParams','skinCommandoDefault_params.asset'),'79721deb6c4df58499b339f81ac8b33d':('UnityEngine.Material','matCommandoDualies.mat')}
    for key,(kind,name) in required.items():
        found=[x for x in catalog if x['key']==key and x['type']==kind]
        if len(found)!=1 or not found[0]['internalId'].endswith('/'+name):raise RuntimeError('Unexpected catalog mapping '+key)
    export=ROOT/read(WORK/'config/reconstruction.json')['projects'][0];base='Assets/RoR2/Base/Characters/Commando/'
    names=['animCommando.controller','mdlCommandoDualiesAvatar.asset','CommandoMesh.asset','GunMesh.asset','GunMesh.001.asset','matCommandoDualies.mat']
    index={}
    for meta in (export/'Assets').rglob('*.meta'):
        match=re.search(r'^guid: ([a-f0-9]{32})',meta.read_text(errors='replace'),re.M)
        if match:index[match[1]]=Path(str(meta)[:-5])
    queue=deque(export/(base+n) for n in names);seen=set();added={}
    while queue:
        src=queue.popleft()
        if src in seen:continue
        seen.add(src)
        if src.suffix=='.dll':continue
        dst=stage/src.relative_to(export/'Assets')
        if not dst.exists():
            dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst);shutil.copy2(Path(str(src)+'.meta'),Path(str(dst)+'.meta'));added[str(src.relative_to(export))]=sha(src)
        if src.read_bytes()[:5]==b'%YAML':
            for guid in re.findall(r'guid:\s*([a-f0-9]{32})',src.read_text()):
                if guid.startswith('0000000000000000'):continue
                target=index.get(guid)
                if not target or not target.is_file():raise RuntimeError('Unresolved default-skin static GUID '+guid)
                queue.append(target)
    r['default_assets']=['Assets/LabLoadingScene/'+str(Path(base+n).relative_to('Assets')) for n in names]
    r['default_added_hashes']=added;r['default_binding_scope']='Explicit diagnostic binding on inactive clone; original Addressables/skin-loader execution unproven'
    write(out/'attempt.json',r)
    queries=[]
    for path in r['default_assets']:
        text=(WORK/'lab-project'/path).read_text();file_id=re.search(r'^--- !u!\d+ &(-?\d+)',text,re.M)[1];queries.append({'path':path,'fileID':file_id})
    write(WORK/'lab-project/Assets/LabReferenceQuery.json',{'attempt':out.name,'output':str(out/'default-asset-identities.json'),'queries':queries})
    print(json.dumps({'added_files':len(added),'assets':len(names),'evidence':str(out.relative_to(ROOT))}))


def pose_prepare():
    """Reuse the passing inactive content recipe, changing only the visual probe."""
    from build import preflight
    preflight();checkpoint=read(WORK/'checkpoints/LAST_KNOWN_GOOD_PREFAB_CONTENT.json')
    if checkpoint['input_id']!=read(WORK/'inventory/files.json')['input_id']:raise RuntimeError('Accepted input differs from prefab checkpoint')
    previous=ROOT/checkpoint['evidence'];stage=WORK/'lab-project/Assets/LabLoadingScene'
    if stage.exists():raise RuntimeError('Previous stage remains; preserve/classify before restoring')
    for name,h in checkpoint['transformations']['original_assemblies'].items():
        if sha(previous/'stage/Plugins'/name)!=h:raise RuntimeError('Archived original assembly drift '+name)
    out=WORK/'experiments/scene-runtime'/now();out.mkdir(parents=True)
    shutil.copytree(previous/'stage',stage)
    r=read(previous/'attempt.json');r.update({'attempt':out.name,'evidence':str(out.relative_to(ROOT)),'stage':str(stage),'pose':True,'parent_evidence':str(previous.relative_to(ROOT)),'status':'restored passing content, visual probe pending'})
    write(out/'attempt.json',r);write(out.parent/'current.json',{'path':str(out.relative_to(ROOT))})
    cfg=read(stage/'Resources/LoadingSceneProbe.json');cfg.update({'attempt':out.name,'pose':True});write(stage/'Resources/LoadingSceneProbe.json',cfg)
    for name in ['LoadingSceneProbe.cs','CommandoPosePreview.cs']:shutil.copy2(ROOT/'tools/unity'/name,stage/name)
    shutil.copy2(ROOT/'tools/unity/CommandoPreview.shader',stage/'Resources/CommandoPreview.shader')
    shutil.copy2(previous/'scene-probe-build.json',WORK/'scene-probe-build.json')
    print(json.dumps({'evidence':str(out.relative_to(ROOT)),'scope':'Transform/renderer-only preview; original gameplay remains inactive'}))


def controller_prepare():
    """Reuse accepted content; replace diagnostic binding with one original request."""
    from build import preflight
    preflight();checkpoint=read(WORK/'checkpoints/LAST_KNOWN_GOOD_PREFAB_CONTENT.json')
    if checkpoint['input_id']!=read(WORK/'inventory/files.json')['input_id']:raise RuntimeError('Accepted input differs')
    previous=ROOT/checkpoint['evidence'];stage=WORK/'lab-project/Assets/LabLoadingScene'
    if stage.exists():raise RuntimeError('Preserve and classify previous stage first')
    for name,h in checkpoint['transformations']['original_assemblies'].items():
        if sha(previous/'stage/Plugins'/name)!=h:raise RuntimeError('Archived original assembly drift '+name)
    out=WORK/'experiments/scene-runtime'/now();out.mkdir(parents=True)
    shutil.copytree(previous/'stage',stage)
    r=read(previous/'attempt.json');r.update({'attempt':out.name,'evidence':str(out.relative_to(ROOT)),'stage':str(stage),'controller':True,'parent_evidence':str(previous.relative_to(ROOT)),'status':'Original controller request pending; no scene/prefab activation'})
    prefab=WORK/'lab-project'/r['prefab'];text=prefab.read_text();key='48ef8327759dd43439416d4823124d9c'
    if not re.search(r'_animatorControllerAddress:\s*\n\s*m_AssetGUID: '+key,text):raise RuntimeError('Original controller address differs')
    write(out/'attempt.json',r);write(out.parent/'current.json',{'path':str(out.relative_to(ROOT))})
    (stage/'Resources/LoadingSceneProbe.json').unlink();(stage/'LoadingSceneProbe.cs').unlink()
    write(stage/'Resources/ControllerAddressProbe.json',{'attempt':out.name,'key':key,'bundle':'commando-prefab-lab','asset':r['default_assets'][0].lower()})
    shutil.copy2(ROOT/'tools/unity/CommandoMaterialPreview.cs',stage/'CommandoMaterialPreview.cs');shutil.copy2(ROOT/'tools/unity/ControllerAddressProbe.cs',stage/'ControllerAddressProbe.cs')
    (stage/'ControllerPreservation').mkdir()
    shutil.copy2(ROOT/'tools/unity/ControllerAddressLink.xml',stage/'ControllerPreservation/link.xml')
    shutil.copy2(previous/'scene-probe-build.json',WORK/'scene-probe-build.json')
    write(out/'prior-art.json',{'reference':'docs/community-prior-art.md','sources':['RoR2EditorKit AddressablesPathDictionary','ThunderKit ImportAddressableCatalog','R2API AddressReferencedAsset'],'decision':'Original providers first, real local initialization, explicit original cleanup scheduler; no fake initialization flags'})
    print(json.dumps({'evidence':str(out.relative_to(ROOT)),'scope':r['status']}))


def avatar_prepare():
    """One original GUID[subobject] request mapped to its recovered standalone Avatar."""
    from build import preflight
    preflight();checkpoint=read(WORK/'checkpoints/LAST_KNOWN_GOOD_CONTROLLER_LOADER.json')
    if checkpoint['input_id']!=read(WORK/'inventory/files.json')['input_id']:raise RuntimeError('Accepted input differs')
    previous=ROOT/checkpoint['evidence'];stage=WORK/'lab-project/Assets/LabLoadingScene'
    if stage.exists():raise RuntimeError('Preserve previous stage first')
    r=read(previous/'attempt.json')
    for name,h in r['original_assemblies'].items():
        if sha(previous/'stage/Plugins'/name)!=h:raise RuntimeError('Archived original assembly drift '+name)
    base=ROOT/r['parent_evidence'];catalog=read(base/'default-skin-addresses.json');identities=read(base/'default-asset-identities.json')
    key='47f06aa0c19f14749840757bbb39d4c8';sub='mdlCommandoDualiesAvatar'
    location=next(x for x in catalog['locations'] if x['key']==key and x['type']=='UnityEngine.Avatar')
    identity=next(x for x in identities['rows'] if x['objectType']=='UnityEngine.Avatar' and x['name']==sub and x['resolved'])
    relative=Path(r['prefab']).relative_to('Assets/LabLoadingScene');prefab=(previous/'stage'/relative).read_text()
    if not re.search(r'_avatarAddress:\s*\n\s*m_AssetGUID: '+key+r'\s*\n\s*m_SubObjectName: '+sub+r'\s*\n',prefab):raise RuntimeError('Original avatar address differs')
    out=WORK/'experiments/scene-runtime'/now();out.mkdir(parents=True);shutil.copytree(previous/'stage',stage)
    r.update({'attempt':out.name,'evidence':str(out.relative_to(ROOT)),'stage':str(stage),'avatar':True,'parent_evidence':str(previous.relative_to(ROOT)),'status':'Original avatar subobject request pending; startup inactive'})
    write(out/'attempt.json',r);write(out.parent/'current.json',{'path':str(out.relative_to(ROOT))})
    write(stage/'Resources/ControllerAddressProbe.json',{'attempt':out.name,'kind':'avatar','key':key,'subObjectName':sub,'runtimeKey':key+'['+sub+']','asset':identity['path'].lower(),'bundle':'commando-prefab-lab'})
    shutil.copy2(ROOT/'tools/unity/CommandoMaterialPreview.cs',stage/'CommandoMaterialPreview.cs');shutil.copy2(ROOT/'tools/unity/ControllerAddressProbe.cs',stage/'ControllerAddressProbe.cs');shutil.copy2(previous/'scene-probe-build.json',WORK/'scene-probe-build.json')
    write(out/'avatar-identity.json',{'original_location':{k:location[k] for k in ['key','internalId','type','provider']},'recovered_identity':identity,'mapping':'Original GUID[subobject] to measured standalone recovered Avatar, not an invented FBX path','prior_art':'RoR2EditorKit BaseGameAssetReferenceTDrawer preserves GUID and subobject separately; original AssetReference.RuntimeKey composes brackets'})
    print(json.dumps({'evidence':str(out.relative_to(ROOT)),'scope':r['status']}))


def skin_prepare():
    """Measure six template paths from serialized references before original baking."""
    from build import preflight
    preflight();checkpoint=read(WORK/'checkpoints/LAST_KNOWN_GOOD_AVATAR_LOADER.json')
    if checkpoint['input_id']!=read(WORK/'inventory/files.json')['input_id']:raise RuntimeError('Accepted input differs')
    previous=ROOT/checkpoint['evidence'];stage=WORK/'lab-project/Assets/LabLoadingScene'
    if stage.exists():raise RuntimeError('Preserve previous stage first')
    r=read(previous/'attempt.json')
    for name,h in r['original_assemblies'].items():
        if sha(previous/'stage/Plugins'/name)!=h:raise RuntimeError('Archived original assembly drift '+name)
    export=ROOT/read(WORK/'config/reconstruction.json')['projects'][0];relative=Path('RoR2/Base/Characters/Commando/skinCommandoDefault_params.asset');src=export/'Assets'/relative;params=src.read_text();skin=(previous/'stage'/relative.with_name('skinCommandoDefault.asset')).read_text()
    if 'baseSkins: []' not in skin:raise RuntimeError('Unexpected base skins')
    key=re.search(r'skinDefParamsAddress:\s*\n\s*m_AssetGUID: ([a-f0-9]{32})',skin)[1]
    if key!='529399f7071eb2641897f2895c5d4ef0':raise RuntimeError('Skin params address drift')
    prefab=(previous/'stage'/Path(r['prefab']).relative_to('Assets/LabLoadingScene')).read_text()
    blocks={m[1]:m[2] for m in re.finditer(r'^--- !u!\d+ &(-?\d+)\n(.*?)(?=^---|\Z)',prefab,re.M|re.S)}
    names={i:re.search(r'^  m_Name: (.*)$',b,re.M)[1] for i,b in blocks.items() if b.startswith('GameObject:')}
    transforms={};go_to_transform={}
    for i,b in blocks.items():
        if b.startswith('Transform:'):
            go=re.search(r'm_GameObject: \{fileID: (-?\d+)',b)[1];parent=re.search(r'm_Father: \{fileID: (-?\d+)',b)[1];transforms[i]=(go,parent);go_to_transform[go]=i
    root_go=re.search(r'rootObject: \{fileID: (-?\d+)',skin)[1];root_transform=go_to_transform[root_go]
    def renderer_path(i):
        go=re.search(r'm_GameObject: \{fileID: (-?\d+)',blocks[i])[1];node=go_to_transform[go];parts=[];seen=set()
        while node!=root_transform:
            if node in seen or node not in transforms:raise RuntimeError('Renderer outside skin root')
            seen.add(node);go,node=transforms[node];parts.append(names[go])
        return '/'.join(reversed(parts))
    renderer_ids=re.findall(r'- renderer: \{fileID: (-?\d+)',params.split('  gameObjectActivations:')[0]);mesh_part=params.split('  meshReplacements:')[1].split('  projectileGhostReplacements:')[0];mesh_ids=re.findall(r'- renderer: \{fileID: (-?\d+)',mesh_part)
    mesh_pairs=re.findall(r'm_AssetGUID: ([a-f0-9]{32})\s+ m_SubObjectName: (\S+)',mesh_part)
    materials=re.findall(r'defaultMaterialAddress:\s*\n\s*m_AssetGUID: ([a-f0-9]{32})',params)
    if len(renderer_ids)!=3 or len(mesh_ids)!=3 or len(mesh_pairs)!=3 or len(set(materials))!=1:raise RuntimeError('Unexpected default skin template contract')
    for field in ['gameObjectActivations','projectileGhostReplacements','minionSkinReplacements','lightReplacements']:
        if field+': []' not in params:raise RuntimeError('Unexpected nonempty '+field)
    out=WORK/'experiments/scene-runtime'/now();out.mkdir(parents=True);shutil.copytree(previous/'stage',stage);shutil.copy2(src,stage/relative);shutil.copy2(Path(str(src)+'.meta'),Path(str(stage/relative)+'.meta'))
    r.update({'attempt':out.name,'evidence':str(out.relative_to(ROOT)),'stage':str(stage),'skin':True,'avatar':False,'parent_evidence':str(previous.relative_to(ROOT)),'status':'Original skin baking pending; startup inactive','skin_params_sha256':sha(src)})
    write(out/'attempt.json',r);write(out.parent/'current.json',{'path':str(out.relative_to(ROOT))})
    root_key=re.search(r'^guid: ([a-f0-9]{32})',(previous/'stage'/Path(str(relative.with_name('skinCommandoDefault.asset'))+'.meta')).read_text(),re.M)[1]
    cfg={'attempt':out.name,'kind':'skin','key':root_key,'asset':('Assets/LabLoadingScene/'+str(relative.with_name('skinCommandoDefault.asset'))).lower(),'bundle':'commando-prefab-lab','paramsKey':key,'paramsAsset':('Assets/LabLoadingScene/'+str(relative)).lower(),'rendererPaths':[renderer_path(i) for i in renderer_ids],'meshPaths':[renderer_path(i) for i in mesh_ids],'meshKeys':[g+'['+n+']' for g,n in mesh_pairs],'materialKey':materials[0]}
    write(stage/'Resources/ControllerAddressProbe.json',cfg);write(out/'skin-contract.json',dict(cfg,root_key_provenance='Diagnostic root uses exported SkinDef GUID; deferred paramsKey is original game address'));shutil.copy2(ROOT/'tools/unity/CommandoMaterialPreview.cs',stage/'CommandoMaterialPreview.cs');shutil.copy2(ROOT/'tools/unity/ControllerAddressProbe.cs',stage/'ControllerAddressProbe.cs')
    recipe=read(previous/'scene-probe-build.json');recipe['prefabAssets']+=['Assets/LabLoadingScene/'+str(relative), 'Assets/LabLoadingScene/'+str(relative.with_name('skinCommandoDefault.asset'))]
    write(WORK/'scene-probe-build.json',recipe)
    print(json.dumps({'evidence':str(out.relative_to(ROOT)),'renderer_paths':cfg['rendererPaths'],'mesh_paths':cfg['meshPaths']}))


def skin_apply_prepare():
    """Add only measured material/mesh locations to the accepted original baking probe."""
    from build import preflight
    preflight();checkpoint=read(WORK/'checkpoints/LAST_KNOWN_GOOD_SKIN_BAKE.json')
    if checkpoint['input_id']!=read(WORK/'inventory/files.json')['input_id']:raise RuntimeError('Accepted input differs')
    previous=ROOT/checkpoint['evidence'];stage=WORK/'lab-project/Assets/LabLoadingScene'
    if stage.exists():raise RuntimeError('Preserve previous stage first')
    r=read(previous/'attempt.json')
    for name,h in r['original_assemblies'].items():
        if sha(previous/'stage/Plugins'/name)!=h:raise RuntimeError('Archived original assembly drift '+name)
    cfg=read(previous/'stage/Resources/ControllerAddressProbe.json');prefix='Assets/LabLoadingScene/';base='RoR2/Base/Characters/Commando/'
    # J26 measured exported identities; inspect their current archived serialization again.
    names=[key.split('[',1)[1].rstrip(']') for key in cfg['meshKeys']];mesh_paths=[base+n+'.asset' for n in names]
    vertices=[]
    for name,path in zip(names,mesh_paths):
        text=(previous/'stage'/path).read_text()
        if re.search(r'^  m_Name: (.*)$',text,re.M)[1]!=name:raise RuntimeError('Mesh name differs')
        vertices.append(int(re.search(r'm_VertexCount: (\d+)',text)[1]))
    material_path=base+'matCommandoDualies.mat';material=(previous/'stage'/material_path).read_text();material_name=re.search(r'^  m_Name: (.*)$',material,re.M)[1]
    if material_name!='matCommandoDualies':raise RuntimeError('Material identity differs')
    out=WORK/'experiments/scene-runtime'/now();out.mkdir(parents=True);shutil.copytree(previous/'stage',stage)
    r.update({'attempt':out.name,'evidence':str(out.relative_to(ROOT)),'stage':str(stage),'skin_apply':True,'parent_evidence':str(previous.relative_to(ROOT)),'status':'Original skin application on inactive model pending'})
    cfg.update({'attempt':out.name,'applySkin':True,'meshAssets':[(prefix+x).lower() for x in mesh_paths],'meshNames':names,'meshVertices':vertices,'materialAsset':(prefix+material_path).lower(),'materialName':material_name})
    write(out/'attempt.json',r);write(out.parent/'current.json',{'path':str(out.relative_to(ROOT))});write(stage/'Resources/ControllerAddressProbe.json',cfg)
    write(out/'skin-application-contract.json',dict(cfg,prior_art='Current original RuntimeSkin.ApplyAsync assigns mesh components and CharacterModel.baseRendererInfos; ModelSkinController cleans returned ownership lists. Community skin guidance distinguishes baking from application.',material_scope='Renderer records only; material update and original model lifecycle inactive'))
    shutil.copy2(ROOT/'tools/unity/CommandoMaterialPreview.cs',stage/'CommandoMaterialPreview.cs');shutil.copy2(ROOT/'tools/unity/ControllerAddressProbe.cs',stage/'ControllerAddressProbe.cs');shutil.copy2(previous/'scene-probe-build.json',WORK/'scene-probe-build.json')
    print(json.dumps({'evidence':str(out.relative_to(ROOT)),'mesh_vertices':vertices,'scope':r['status']}))

def material_render_prepare():
    """L11-a: restore J38 and add only original slot assignment plus owned display copies."""
    from build import preflight
    preflight();checkpoint=read(WORK/'checkpoints/LAST_KNOWN_GOOD_SKIN_APPLICATION.json')
    if checkpoint['input_id']!=read(WORK/'inventory/files.json')['input_id']:raise RuntimeError('Accepted input differs')
    previous=ROOT/checkpoint['evidence'];stage=WORK/'lab-project/Assets/LabLoadingScene'
    if stage.exists():raise RuntimeError('Preserve previous stage first')
    r=read(previous/'attempt.json')
    for name,h in r['original_assemblies'].items():
        if sha(previous/'stage/Plugins'/name)!=h:raise RuntimeError('Archived original assembly drift '+name)
    out=WORK/'experiments/scene-runtime'/now();out.mkdir(parents=True);shutil.copytree(previous/'stage',stage)
    cfg=read(stage/'Resources/ControllerAddressProbe.json');cfg.update({'attempt':out.name,'materialRender':True})
    r.update({'attempt':out.name,'evidence':str(out.relative_to(ROOT)),'stage':str(stage),'skin_apply':True,'material_render':True,'parent_evidence':str(previous.relative_to(ROOT)),'status':'L11-a original renderer assignment and owned Android material display pending'})
    write(out/'attempt.json',r);write(out.parent/'current.json',{'path':str(out.relative_to(ROOT))});write(stage/'Resources/ControllerAddressProbe.json',cfg)
    for name in ['ControllerAddressProbe.cs','CommandoMaterialPreview.cs','CommandoMaterialPreview.shader','CommandoPreview.shader']:shutil.copy2(ROOT/'tools/unity'/name,stage/('Resources/'+name if name.endswith('.shader') else name))
    write(out/'material-render-contract.json',{'source':'J38 accepted skin application','prior_art':'Pinned RoR2EditorKit ShaderPostprocessor is editor-only; original CharacterModel selection is invoked without lifecycle','scope':'Three original renderer slots then detached owned shader material copies; no gameplay/platform/audio/startup'})
    shutil.copy2(previous/'scene-probe-build.json',WORK/'scene-probe-build.json')
    print(json.dumps({'evidence':str(out.relative_to(ROOT)),'scope':r['status']}))


def state_tick_prepare():
    """One scheduling precursor, on the accepted material/content closure."""
    from build import preflight
    preflight();checkpoint=read(WORK/'checkpoints/LAST_KNOWN_GOOD_MATERIAL_RENDERING.json')
    if checkpoint['input_id']!=read(WORK/'inventory/files.json')['input_id']:raise RuntimeError('Accepted input differs')
    previous=ROOT/checkpoint['evidence'];stage=WORK/'lab-project/Assets/LabLoadingScene'
    if stage.exists():raise RuntimeError('Preserve previous stage first')
    r=read(previous/'attempt.json')
    for name,h in r['original_assemblies'].items():
        if sha(previous/'stage/Plugins'/name)!=h:raise RuntimeError('Archived original assembly drift '+name)
    out=WORK/'experiments/scene-runtime'/now();out.mkdir(parents=True);shutil.copytree(previous/'stage',stage)
    r.update({'attempt':out.name,'evidence':str(out.relative_to(ROOT)),'stage':str(stage),'state_tick':True,'parent_evidence':str(previous.relative_to(ROOT)),'status':'Original state scheduling precursor pending; no character or authority'})
    cfg=read(stage/'Resources/ControllerAddressProbe.json');cfg['attempt']=out.name
    write(stage/'Resources/ControllerAddressProbe.json',cfg);write(stage/'Resources/EntityStateTickProbe.json',{'attempt':out.name})
    shutil.copy2(ROOT/'tools/unity/EntityStateTickProbe.cs',stage/'EntityStateTickProbe.cs')
    write(out/'attempt.json',r);write(out.parent/'current.json',{'path':str(out.relative_to(ROOT))});shutil.copy2(previous/'scene-probe-build.json',WORK/'scene-probe-build.json')
    print(json.dumps({'evidence':str(out.relative_to(ROOT)),'scope':r['status']}))


def startup_prepare(loading_scene=False, application_awake=False, global_textures=False, interpolation=False, fps_queue=False, volume=False, volume_order=False, ngss=False, integration=False):
    """Restore accepted runtime and isolate the first original startup phase."""
    from build import preflight
    preflight();checkpoint=read(WORK/'checkpoints'/('LAST_KNOWN_GOOD_NGSS.json' if integration else 'LAST_KNOWN_GOOD_VOLUME_ORDER.json' if ngss else 'LAST_KNOWN_GOOD_VOLUME.json' if volume_order else 'LAST_KNOWN_GOOD_FPS_QUEUE.json' if volume else 'LAST_KNOWN_GOOD_INTERPOLATION.json' if fps_queue else 'LAST_KNOWN_GOOD_GLOBAL_TEXTURES.json' if interpolation else 'LAST_KNOWN_GOOD_APPLICATION_AWAKE.json' if global_textures else 'LAST_KNOWN_GOOD_STARTUP_LOADING_SCENE.json' if application_awake else 'LAST_KNOWN_GOOD_STARTUP_SEGMENT.json' if loading_scene else 'LAST_KNOWN_GOOD_SKIN_APPLICATION.json'))
    if checkpoint['input_id']!=read(WORK/'inventory/files.json')['input_id']:raise RuntimeError('Accepted input differs')
    previous=ROOT/checkpoint['evidence'];stage=WORK/'lab-project/Assets/LabLoadingScene'
    if stage.exists():raise RuntimeError('Preserve previous stage first')
    r=read(previous/'attempt.json')
    for name,h in r['original_assemblies'].items():
        if sha(previous/'stage/Plugins'/name)!=h:raise RuntimeError('Archived original assembly drift '+name)
    out=WORK/'experiments/scene-runtime'/now();out.mkdir(parents=True);shutil.copytree(previous/'stage',stage)
    r.update({'attempt':out.name,'evidence':str(out.relative_to(ROOT)),'stage':str(stage),'startup':True,'controller':False,'skin':False,'skin_apply':False,'avatar':False,'parent_evidence':str(previous.relative_to(ROOT)),'status':'Original startup PreFrame and independent profile filesystem candidate pending'})
    (stage/'ControllerAddressProbe.cs').unlink(missing_ok=True);(stage/'Resources/ControllerAddressProbe.json').unlink(missing_ok=True)
    shutil.copy2(ROOT/'tools/unity/AudioAssetProbe.cs',stage/'AudioAssetProbe.cs')
    shutil.copy2(ROOT/'tools/unity/StartupSegmentProbe.cs',stage/'StartupSegmentProbe.cs');write(stage/'Resources/StartupSegmentProbe.json',{'attempt':out.name,'loadingScene':loading_scene,'applicationAwake':application_awake})
    write(out/'attempt.json',r);write(out.parent/'current.json',{'path':str(out.relative_to(ROOT))});shutil.copy2(previous/'scene-probe-build.json',WORK/'scene-probe-build.json')
    for name in ['original-metadata.json','reflection-metadata.json']:shutil.copy2(WORK/'experiments/startup-boundary'/name,out/name)
    write(out/'startup-contract.json',{'segment':'Original InitializeGameRoutine first MoveNext, then reviewed PreFrame enumerator only; Awake and later startup remain inactive','expected_targets':['FlashWindow.Init'],'predicted_boundary':'FlashWindow cctor calls kernel32 GetCurrentProcessId; establish actual device outcome without patching','profile':'Original Zio SubFileSystem under fresh owned persistent directory; read-only content view, no vanilla saves or global filesystem assignment','prior_art':'ProperSave filesystem policy separation; community-prior-art.md startup trace; actual original DLL IL rechecked'})
    if loading_scene:
        r['startup_loading_scene']=True;r['status']='Original recovered loading-scene handoff pending';write(out/'attempt.json',r)
        contract=read(out/'startup-contract.json');contract.update({'segment':'Original PreFrame then actual recovered loadingbasic and two original loading UI yields; stop before EnableBehaviours', 'predicted_boundary':'Recovered Canvas/percentage and enable-list identities; no new adapter'});write(out/'startup-contract.json',contract)
    if application_awake:
        r['startup_application_awake']=True;r['status']='Original recovered application Awake pending';write(out/'attempt.json',r)
        contract=read(out/'startup-contract.json');contract.update({'segment':'Accepted loading UI then explicitly invoke original Awake on inactive recovered component; no automatic Start/Update', 'predicted_boundary':'Original loading flag prevents duplicate coroutine; real singleton, build ID and assembly types must match; entitlement subscriptions do not assert entitlement success'});write(out/'startup-contract.json',contract)
    if global_textures:
        import struct
        scene=(stage/'RoR2/Base/Scenes/loadingbasic/loadingbasic.unity').read_text()
        block=re.search(r'^--- !u!114 &218\n.*?(?=^---|\Z)',scene,re.M|re.S).group(0)
        pairs=[('warpRampTexture','warpRampShaderVariableName'),('eliteRampTexture','eliteRampShaderVariableName'),('snowMicrofacetTexture','snowMicrofacetNoiseVariableName')]
        textures=[];identities=[]
        for field,variable_field in pairs:
            match=re.search(r'^  '+field+r': \{fileID: (\d+), guid: ([a-f0-9]+), type: 3\}',block,re.M)
            if not match or match[1]!='2800000':raise RuntimeError('Unreviewed texture reference '+field)
            guid=match[2];matches=[p for p in stage.rglob('*.png.meta') if 'guid: '+guid in p.read_text()]
            if len(matches)!=1:raise RuntimeError('Ambiguous texture GUID '+guid)
            source=Path(str(matches[0])[:-5]);data=source.read_bytes()
            if data[:8]!=b'\x89PNG\r\n\x1a\n':raise RuntimeError('Expected PNG source')
            width,height=struct.unpack('>II',data[16:24]);variable=re.search(r'^  '+variable_field+r': (.+)$',block,re.M)[1]
            textures.append({'name':source.stem,'variable':variable,'width':width,'height':height})
            identities.append({'field':field,'guid':guid,'fileID':match[1],'source':str(source.relative_to(stage)),'sha256':sha(source),'expected':textures[-1]})
        cfg=read(stage/'Resources/StartupSegmentProbe.json');cfg.update({'globalTextures':True,'textures':textures});write(stage/'Resources/StartupSegmentProbe.json',cfg)
        write(out/'texture-identities.json',identities);r['startup_global_textures']=True;r['status']='Original global texture Start pending';write(out/'attempt.json',r)
        contract=read(out/'startup-contract.json');contract.update({'segment':'Accepted recovered Awake then original GlobalShaderTextures.Start on actual inactive component','assertions':'Three serialized GUID/PNG identities and globals; clear only measured globals before original invocation and restore previous values afterward; no rendering claim'});write(out/'startup-contract.json',contract)
    if interpolation:
        cfg=read(stage/'Resources/StartupSegmentProbe.json');cfg['interpolation']=True;write(stage/'Resources/StartupSegmentProbe.json',cfg)
        r['startup_interpolation']=True;r['status']='Original interpolation methods pending';write(out/'attempt.json',r)
        contract=read(out/'startup-contract.json');contract.update({'segment':'Accepted texture probe then original interpolation Start/FixedUpdate/Update under diagnostic scheduling','assertions':'Initial fallback, nine real fixed samples/eight independent render timing comparisons, two-sample history and previous-state restoration; no character motion or automatic lifecycle claim'});write(out/'startup-contract.json',contract)
    if fps_queue:
        cfg=read(stage/'Resources/StartupSegmentProbe.json');cfg['fpsQueue']=True;write(stage/'Resources/StartupSegmentProbe.json',cfg)
        r['startup_fps_queue']=True;r['status']='Original FPSQueue callback pending';write(out/'attempt.json',r)
        contract=read(out/'startup-contract.json');contract.update({'segment':'Accepted component probes then original FPSQueue.Start and only its newly registered callback','assertions':'36 measured frame samples, rolling average/index/turn checks, wait-slot wrap and throttling decisions; restore original subscription/static state; never invoke unrelated subscribers'});write(out/'startup-contract.json',contract)
    if volume:
        scene=(stage/'RoR2/Base/Scenes/loadingbasic/loadingbasic.unity').read_text();profiles=[];identities=[]
        for fid in [219,222]:
            block=re.search(r'^--- !u!114 &'+str(fid)+r'\n.*?(?=^---|\Z)',scene,re.M|re.S)[0]
            guid=re.search(r'sharedProfile: \{fileID: 11400000, guid: ([a-f0-9]+), type: 2\}',block)[1]
            matches=[p for p in stage.rglob('*.asset.meta') if 'guid: '+guid in p.read_text()]
            if len(matches)!=1:raise RuntimeError('Ambiguous volume profile '+guid)
            source=Path(str(matches[0])[:-5]);text=source.read_text();blocks=dict(re.findall(r'^--- !u!114 &(\d+)\n(.*?)(?=^---|\Z)',text,re.M|re.S));root=blocks['11400000'];settings=[];refs=re.findall(r'^  - \{fileID: (\d+)\}',root,re.M)
            for ref in refs:
                b=blocks[ref];settings.append({'name':re.search(r'^  m_Name: (.+)$',b,re.M)[1],'active':re.search(r'^  active: (\d+)$',b,re.M)[1]=='1','enabled':re.search(r'^  enabled:\n    overrideState: \d+\n    value: (\d+)',b,re.M)[1]=='1'})
            profiles.append({'name':re.search(r'^  m_Name: (.+)$',root,re.M)[1],'priority':float(re.search(r'^  priority: (.+)$',block,re.M)[1]),'settings':settings});identities.append({'volume_fileID':fid,'profile_guid':guid,'source':str(source.relative_to(stage)),'sha256':sha(source),'setting_fileIDs':refs,'expected':profiles[-1]})
        cfg=read(stage/'Resources/StartupSegmentProbe.json');cfg.update({'volume':True,'volumes':profiles});write(stage/'Resources/StartupSegmentProbe.json',cfg);write(out/'volume-identities.json',identities)
        r['startup_volume']=True;r['status']='Original first postprocessing volume lifecycle pending';write(out/'attempt.json',r)
        contract=read(out/'startup-contract.json');contract.update({'segment':'Audit both recovered profiles, execute first volume OnEnable/Update/OnDisable only','assertions':'Exact profile/settings identity and balanced manager registrations; restore component fields; no renderer or second-volume lifecycle claim'});write(out/'startup-contract.json',contract)
    if volume_order:
        cfg=read(stage/'Resources/StartupSegmentProbe.json');cfg['volumeOrder']=True;write(stage/'Resources/StartupSegmentProbe.json',cfg)
        r['startup_volume_order']=True;r['status']='Original volume pair priority ordering pending';write(out/'attempt.json',r)
        contract=read(out/'startup-contract.json');contract.update({'segment':'Both original volume lifecycles registered in reverse priority order; original GrabVolumes query','assertions':'Original manager returns ascending priority for actual layer and excludes pair from zero mask; registrations and queried list return to baseline; component fields restored; no rendering claim'});write(out/'startup-contract.json',contract)
    if ngss:
        import struct
        source=stage/'Scripts/Assembly-CSharp/NGSS_Local.cs';expected=r['copied_source_hashes']['Assets/Scripts/Assembly-CSharp/NGSS_Local.cs']
        if sha(source)!=expected:raise RuntimeError('Recovered NGSS source drift')
        scene=(stage/'RoR2/Base/Scenes/loadingbasic/loadingbasic.unity').read_text();block=re.search(r'^--- !u!114 &225\n.*?(?=^---|\Z)',scene,re.M|re.S)[0]
        guid=re.search(r'NGSS_NOISE_TEXTURE: \{fileID: 2800000, guid: ([a-f0-9]+), type: 3\}',block)[1];matches=[p for p in stage.rglob('*.png.meta') if 'guid: '+guid in p.read_text()]
        if len(matches)!=1:raise RuntimeError('Ambiguous noise texture')
        noise=Path(str(matches[0])[:-5]);width,height=struct.unpack('>II',noise.read_bytes()[16:24]);fields={k:float(v) for k,v in re.findall(r'^  (NGSS_\w+): (-?[\d.]+)$',block,re.M)}
        values={'NGSS_TEST_SAMPLERS':max(4,min(fields['NGSS_SAMPLING_TEST'],fields['NGSS_SAMPLING_FILTER'])),'NGSS_PCSS_FILTER_LOCAL_MIN':fields['NGSS_PCSS_SOFTNESS_NEAR'],'NGSS_PCSS_FILTER_LOCAL_MAX':fields['NGSS_PCSS_SOFTNESS_FAR'],'NGSS_NOISE_TO_DITHERING_SCALE':fields['NGSS_NOISE_TO_DITHERING_SCALE'],'NGSS_FILTER_SAMPLERS':fields['NGSS_SAMPLING_FILTER'],'NGSS_GLOBAL_OPACITY':1-fields['NGSS_SHADOWS_OPACITY'],'NGSS_LOCAL_SAMPLING_DISTANCE':fields['NGSS_SAMPLING_DISTANCE'],'NGSS_LOCAL_NORMAL_BIAS':fields['NGSS_NORMAL_BIAS']*0.1}
        cfg=read(stage/'Resources/StartupSegmentProbe.json');cfg.update({'ngss':True,'noise':{'name':noise.stem,'width':width,'height':height},'ngssGlobals':[{'name':k,'value':v} for k,v in values.items()]});write(stage/'Resources/StartupSegmentProbe.json',cfg)
        write(out/'ngss-provenance.json',{'code':'Locally recompiled recovered source, NOT preserved original Assembly-CSharp DLL','source':str(source.relative_to(stage)),'source_sha256':expected,'noise_guid':guid,'noise_source':str(noise.relative_to(stage)),'noise_sha256':sha(noise),'serialized_fields':fields,'expected_globals':values})
        r['startup_ngss']=True;r['status']='Recovered NGSS initialization pending';write(out/'attempt.json',r)
        contract=read(out/'startup-contract.json');contract.update({'segment':'Locally recompiled recovered NGSS OnEnable/Update/OnDisable, serialized noise path only','assertions':'Noise identity, eight shader globals, initialized/disabled state and previous-global restoration; no fallback-resource or rendered-shadow proof'});write(out/'startup-contract.json',contract)
    if integration:
        cfg=read(stage/'Resources/StartupSegmentProbe.json');cfg['integration']=True;write(stage/'Resources/StartupSegmentProbe.json',cfg)
        r['startup_integration']=True;r['status']='Automatic recovered host startup before audio pending';write(out/'attempt.json',r)
        contract=read(out/'startup-contract.json');contract.update({'segment':'Fresh actual recovered host owns original routine; its first yield establishes loading state, then Unity activation invokes automatic callbacks; advance through component enabling only','assertions':'Exact eight-MonoBehaviour closure including FontCleaner, automatic Start/Update/FixedUpdate/LateUpdate observations, six active enabled components, no new errors or filesystem assignment; next routine instruction is Wwise and is not executed'});write(out/'startup-contract.json',contract)
    print(json.dumps({'evidence':str(out.relative_to(ROOT)),'scope':r['status']}))


def audio_assets_prepare(native_availability=False):
    """J51 measured prefab closure; asset loading only, no audio activation."""
    startup_prepare(integration=True)
    out=ROOT/read(WORK/'experiments/scene-runtime/current.json')['path'];r=read(out/'attempt.json');stage=Path(r['stage'])
    audit=WORK/'experiments/audio-boundary/20260914T032612Z'
    identities=read(audit/'identities.json')['rows']
    if len(identities)!=8 or not all(x['resolved'] and not x['error'] for x in identities):raise RuntimeError('Audio identity gate failed')
    export=ROOT/read(WORK/'config/reconstruction.json')['projects'][0]/'Assets'
    closure=read(audit/'serialized-closure.json')
    if closure['unresolved']:raise RuntimeError('Unresolved audio closure')
    for row in closure['files']:
        src=export/row['path']
        if sha(src)!=row['sha256']:raise RuntimeError('Audio input drift '+row['path'])
        if src.suffix=='.dll':continue
        dst=stage/row['path'];dst.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(src,dst);shutil.copy2(Path(str(src)+'.meta'),Path(str(dst)+'.meta'))
    names=['WwiseGlobal','AudioManager'];assets=['Assets/LabLoadingScene/RoR2/Base/Core/Audio/'+n+'.prefab' for n in names]
    cfg={'names':names,'paths':['Prefabs/'+n for n in names],'keys':['8efd031dc149abb42a4ba4021856af9d','d42d5c95eee66a348a4c4abf71e0352b'],'assets':assets}
    cfg['nativeAvailability']=native_availability
    write(stage/'Resources/AudioAssetProbe.json',cfg);shutil.copy2(ROOT/'tools/unity/AudioAssetProbe.cs',stage/'AudioAssetProbe.cs')
    build=read(WORK/'scene-probe-build.json');build['prefabAssets']+=assets;write(WORK/'scene-probe-build.json',build)
    r['audio_assets']=True;write(out/'attempt.json',r);write(out/'audio-closure.json',closure);write(out/'audio-config.json',cfg)


def audio_guard_prepare():
    from boundaries import probe_tool
    audio_assets_prepare(native_availability=True)
    out=ROOT/read(WORK/'experiments/scene-runtime/current.json')['path'];r=read(out/'attempt.json');stage=Path(r['stage'])
    original=stage/'Plugins/RoR2.dll';candidate=out/'RoR2.audio-unavailable.dll'
    command=probe_tool()
    result=json.loads(run(command+['--audio-guard',original,candidate,r['original_assemblies']['RoR2.dll'],game()/'Risk of Rain 2_Data/Managed'],timeout=120).stdout)
    write(out/'audio-guard-transformation.json',result);shutil.copy2(original,out/'RoR2.original.dll');shutil.copy2(candidate,original)
    r['transformed_assemblies']={'RoR2.dll':result['output_sha256']};r['audio_guard']=True;write(out/'attempt.json',r)
    cfg=read(stage/'Resources/StartupSegmentProbe.json');cfg['audioGuard']=True;write(stage/'Resources/StartupSegmentProbe.json',cfg)


def profile_binding_prepare():
    audio_guard_prepare()
    out=ROOT/read(WORK/'experiments/scene-runtime/current.json')['path'];r=read(out/'attempt.json');stage=Path(r['stage'])
    cfg=read(stage/'Resources/StartupSegmentProbe.json');cfg['profileBinding']=True;write(stage/'Resources/StartupSegmentProbe.json',cfg)
    r['profile_binding']=True;write(out/'attempt.json',r)
    write(out/'profile-binding-contract.json',{'scope':'Temporary actual globals; original config writer/reader; no coroutine filesystem/platform continuation','app_data':'Writable Config and RunReports role; not read-only content','profiles':'Separate Android-only writable root; sentinel only, not vanilla profile','restore':'Both globals restored before return; unique owned temporary files removed'})


def steam_boundary_prepare():
    profile_binding_prepare()
    out=ROOT/read(WORK/'experiments/scene-runtime/current.json')['path'];r=read(out/'attempt.json');stage=Path(r['stage'])
    cfg=read(stage/'Resources/StartupSegmentProbe.json');cfg['steamBoundary']=True;write(stage/'Resources/StartupSegmentProbe.json',cfg)
    r['steam_boundary']=True;write(out/'attempt.json',r)
    write(out/'steam-boundary-contract.json',{'scope':'Original Init callback registration, load result and unload; no PlatformSystems.Init','expected':'Load returns false; no authenticated/owned state is manufactured','guards':'No existing app-id file or Steam/profile state; original callbacks restored','limitations':'Original catch hides failure cause; false alone does not identify which native or mandatory check failed'})


def steam_exception_prepare():
    steam_boundary_prepare()
    out=ROOT/read(WORK/'experiments/scene-runtime/current.json')['path'];r=read(out/'attempt.json');stage=Path(r['stage'])
    cfg=read(stage/'Resources/StartupSegmentProbe.json');cfg['steamException']=True;write(stage/'Resources/StartupSegmentProbe.json',cfg)
    r['steam_exception']=True;write(out/'attempt.json',r)
    write(out/'steam-exception-contract.json',{'scope':'Fresh process original private constructor before any load callback; observe first inner exception','assembly_changes':'No new transformation beyond accepted no-audio getter','pass':'No prior Facepunch singleton; original constructor exception recorded; no manager/cloud state','limits':'Original callback false is prior J58 evidence, not repeated in this mode; do not infer subscription check ran'})
