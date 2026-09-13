"""Bounded dependency analysis and attributed editor/device experiments."""
from common import *
import shutil

CECIL = Path('/Applications/Unity/Hub/Editor/2021.3.33f1/Unity.app/Contents/MonoBleedingEdge/lib/mono/gac/Mono.Cecil/0.11.1.0__0738eb9f132ed756/Mono.Cecil.dll')

def probe_tool():
    out = WORK/'tools/assembly-probe'
    run([Path.home()/'.local/share/dotnet/dotnet', 'build', ROOT/'tools/AssemblyProbe/AssemblyProbe.csproj', '-o', out, '-p:CecilPath='+str(CECIL), '--nologo'], timeout=120)
    return [Path.home()/'.local/share/dotnet/dotnet', out/'AssemblyProbe.dll']

def inspect_assembly(command, path, types):
    return json.loads(run(command+[path]+list(types), timeout=120).stdout)

def dependency_boundaries():
    from build import preflight
    preflight()
    out = WORK/'experiments/dependency-boundaries'/now();out.mkdir(parents=True)
    source = game()/'Risk of Rain 2_Data/Managed'
    exported = ROOT/read(WORK/'config/reconstruction.json')['projects'][0]/'Assets/Plugins'
    command = probe_tool()
    # Identifiers come from the recorded first failure; report matches against this accepted input.
    cases = {
        'Rewired_Core': ['XYkxBUorLhNyuqgbpljAlCPZHrZt','aptRzjbDAPWNsbxwvLLRSACIDzbFA'],
        'Rewired_Windows': ['LsIeGOGWGXddhqfyfQlehckkVtKeA','ynVAoVvdlVjydgSuoRhhoaeTOXsG'],
    }
    comparisons=[]
    for name, types in cases.items():
        original=inspect_assembly(command, source/(name+'.dll'), types)
        export=inspect_assembly(command, exported/(name+'.dll'), types)
        write(out/('original-'+name+'.json'), original);write(out/('export-'+name+'.json'),export)
        if {t['name'] for t in original['types']} != set(types):raise RuntimeError('Recorded conflict type no longer matches input')
        for t in original['types']:
            other=next(x for x in export['types'] if x['name']==t['name'])
            before={m['name'] for m in t['methods']};after={m['name'] for m in other['methods']}
            comparisons.append({'assembly':name,'type':t['name'],'original_sha256':original['sha256'],'export_sha256':export['sha256'],'original_method_count':len(before),'export_method_count':len(after),'added_methods':sorted(after-before)})
    selected=['RoR2.Trajectory','RoR2.ProcChainMask','RoR2.ProcType']
    game_probe=inspect_assembly(command,source/'RoR2.dll',selected);write(out/'ror2-selected.json',game_probe)
    if {t['name'] for t in game_probe['types']} != set(selected):raise RuntimeError('Selected game types changed')
    inventory=read(WORK/'inventory/managed.json');ror2=next(a for a in inventory if a['name']=='RoR2')
    result={'success':True,'input_id':read(WORK/'inventory/files.json')['input_id'],'comparisons':comparisons,
      'rewired_consumed_members':[m for m in ror2['memberReferences'] if m.startswith('Rewired.')],
      'selected_probe':{'assembly_sha256':game_probe['sha256'],'types':selected,
        'assertions':['gravity -10, launch speed 10: apex 5 and equal-height flight duration 2','origin (1,2,3), velocity (4,10,-2), t=2, gravity -10: position (9,2,-1)','proc mask add/check/idempotent add/remove preserves independent bits'],
        'scope':'Original method IL slice; does not establish full closure, entity states, character simulation or startup'},
      'next_candidate':'Original input Rewired DLLs instead of export-modified DLLs; explicitly root and invoke recorded conflicting overrides',
      'platform_gate':'Full game startup remains blocked pending lawful platform/native lifecycle; no services run in these metadata probes',
      'evidence':str(out.relative_to(ROOT))}
    write(out/'result.json',result);write(out.parent/'latest.json',{'path':str(out.relative_to(ROOT)),'success':True})
    print(json.dumps({k:v for k,v in result.items() if k not in ['rewired_consumed_members','comparisons']},indent=2))

def rewired_original():
    """One J09 hypothesis: preserve original DLL bytes and exercise both disputed slots."""
    from build import preflight, build
    from device import Device
    preflight()
    out=WORK/'experiments/rewired-original'/now();out.mkdir(parents=True)
    project=WORK/'lab-project';assets=project/'Assets';stage=assets/'LabBoundary';stage.mkdir(exist_ok=True)
    if any(stage.iterdir()):raise RuntimeError('Previous boundary stage remains; inspect before replacing it')
    manifest=project/'Packages/manifest.json';prior=manifest.read_bytes();(out/'packages-before.json').write_bytes(prior)
    cfg=read(manifest);cfg['dependencies']['com.unity.ugui']='1.0.0';write(manifest,cfg)
    source=game()/'Risk of Rain 2_Data/Managed';inputs={}
    for name in ['Rewired_Core','Rewired_Windows']:
        p=source/(name+'.dll');shutil.copy2(p,stage/p.name);inputs[name]=sha(p)
    shutil.copy2(ROOT/'tools/unity/MetadataDispatchProbe.cs',stage/'MetadataDispatchProbe.cs')
    resources=stage/'Resources';resources.mkdir()
    cases=[{'assembly':'Rewired_Core','type':'aptRzjbDAPWNsbxwvLLRSACIDzbFA','baseType':'XYkxBUorLhNyuqgbpljAlCPZHrZt','method':'pkYCJDATsXrGjwAAsanbUWnFZDuRA','expected':1},
      {'assembly':'Rewired_Windows','type':'ynVAoVvdlVjydgSuoRhhoaeTOXsG','baseType':'LsIeGOGWGXddhqfyfQlehckkVtKeA','method':'BqfWJmaiaKJdLpNHjoVEFpQRRdvQ','field':'YEEPIUaMEMlmDnBYNlKvPNJdDEiIA','fieldValue':37,'expected':37}]
    write(resources/'MetadataDispatchProbe.json',{'attempt':out.name,'cases':cases})
    import xml.etree.ElementTree as ET
    linker=ET.Element('linker')
    for c in cases:
        a=ET.SubElement(linker,'assembly',{'fullname':c['assembly']})
        for name in [c['type'],c['baseType']]:ET.SubElement(a,'type',{'fullname':name,'preserve':'all'})
    ET.ElementTree(linker).write(stage/'link.xml')
    result={'success':False,'attempt':out.name,'input_id':read(WORK/'inventory/files.json')['input_id'],'original_assemblies':inputs,'scope':'J09 conflicting virtual slots only; no input manager/controller/native backend initialized','stage':str(stage)}
    write(out/'attempt.json',result)
    d=Device();had=d.exists()
    try:
        built=build('vulkan',True);result['build']=built
        result['install']=d.install(built['apk']);d.launch();result['sync']=d.sync();result['runtime']=d.launch()
        runtime=read(WORK/'device/runtime.json');report=json.loads(d.sh('cat',runtime['persistentDataPath']+'/metadata-dispatch.json'))
        write(out/'dispatch.json',report)
        result['success']=report['success'] and report['attempt']==out.name and str(report['pid'])==result['runtime']['pid']
        d.collect('all',out);result['report']=report
    except Exception as e:
        result['error']=str(e)
        if 'install' in result:
            try:d.collect('all',out)
            except Exception as capture:result['capture_error']=str(capture)
    finally:
        if not had and (WORK/'device/installed.json').exists():
            try:result['cleanup']=d.reset()
            except Exception as e:result['cleanup_error']=str(e);result['success']=False
        # Keep failed stage intact for first-error repair. Passing inputs are copied to evidence
        # before removing only this experiment's owned stage; package config stays explicit.
        if result['success']:
            shutil.copytree(stage,out/'stage');shutil.rmtree(stage)
            meta=stage.with_suffix('.meta')
            if meta.exists():meta.unlink()
        write(out/'result.json',result);write(out.parent/'latest.json',{'path':str(out.relative_to(ROOT)),'success':result['success']})
    print(json.dumps({'success':result['success'],'evidence':str(out.relative_to(ROOT)),'error':result.get('error')},indent=2))
    if not result['success']:raise RuntimeError('Rewired original experiment failed; inspect '+str(out))

def collections_runtime():
    """One pinned package candidate; editor result and Android result stay distinct."""
    from build import preflight, build, editor
    from device import Device
    preflight()
    out=WORK/'experiments/collections-runtime'/now();out.mkdir(parents=True)
    project=WORK/'lab-project';stage=project/'Assets/LabCollections'
    if stage.exists():raise RuntimeError('Prior collections stage remains; inspect first')
    stage.mkdir();resources=stage/'Resources';resources.mkdir()
    manifest=project/'Packages/manifest.json';(out/'packages-before.json').write_bytes(manifest.read_bytes())
    cfg=read(manifest);cfg['dependencies'].update({'com.unity.collections':'1.2.4','com.unity.burst':'1.8.11','com.unity.mathematics':'1.2.1'});write(manifest,cfg)
    shutil.copy2(ROOT/'tools/unity/CollectionsRuntimeProbe.cs',stage/'CollectionsRuntimeProbe.cs')
    write(resources/'CollectionsRuntimeProbe.json',{'attempt':out.name})
    result={'success':False,'attempt':out.name,'packages':{k:cfg['dependencies'][k] for k in ['com.unity.collections','com.unity.burst','com.unity.mathematics']},'scope':'Representative allocation/job/slice/disposal candidate; not full game package API/layout or reconstructed Play Mode acceptance'}
    write(out/'attempt.json',result);d=Device();had=d.exists()
    try:
        built=build('vulkan',True);result['build']=built
        # Build is terminal before entering Play Mode on the same editor.
        result['editor_call']=editor('lab','play')
        editor_report=Path.home()/'Library/Application Support/PortingLab/RoR2 Porting Lab/collections-probe.json'
        if editor_report.exists():
            r=read(editor_report);write(out/'editor-probe.json',r)
            result['editor_success']=r['success'] and r['attempt']==out.name
        else:result['editor_success']=False;result['editor_report_missing']=str(editor_report)
        result['install']=d.install(built['apk']);d.launch();result['sync']=d.sync();result['runtime']=d.launch()
        runtime=read(WORK/'device/runtime.json');r=json.loads(d.sh('cat',runtime['persistentDataPath']+'/collections-probe.json'));write(out/'android-probe.json',r)
        result['android_success']=r['success'] and r['attempt']==out.name and str(r['pid'])==result['runtime']['pid']
        result['success']=result['editor_success'] and result['android_success'];result['android_burst_executed']=r['burstExecuted']
        d.collect('all',out)
    except Exception as e:
        result['error']=str(e)
        if 'install' in result:
            try:d.collect('all',out)
            except Exception as capture:result['capture_error']=str(capture)
    finally:
        if not had and (WORK/'device/installed.json').exists():
            try:result['cleanup']=d.reset()
            except Exception as e:result['cleanup_error']=str(e);result['success']=False
        if result['success']:
            shutil.copytree(stage,out/'stage');shutil.rmtree(stage)
            meta=stage.with_suffix('.meta')
            if meta.exists():meta.unlink()
        write(out/'result.json',result);write(out.parent/'latest.json',{'path':str(out.relative_to(ROOT)),'success':result['success']})
    print(json.dumps({'success':result['success'],'evidence':str(out.relative_to(ROOT)),'error':result.get('error')},indent=2))
    if not result['success']:raise RuntimeError('Collections candidate incomplete; inspect '+str(out))

def ror2_slice(full_original=False):
    """Retain original self-contained game method IL; three measured cold starts."""
    from build import preflight, build
    from device import Device
    import time
    preflight()
    out=WORK/'experiments'/('original-closure-runtime' if full_original else 'ror2-slice')/now();out.mkdir(parents=True)
    stage=WORK/'lab-project/Assets'/('LabOriginalClosure' if full_original else 'LabRoR2Slice')
    if full_original:
        prior=read(ROOT/read(WORK/'experiments/original-closure/current.json')['path']/'result.json')
        if not prior['success']:raise RuntimeError('Original closure build must pass first')
        for name,h in prior['original_assemblies'].items():
            if sha(stage/name)!=h:raise RuntimeError('Original assembly drift: '+name)
        provenance={'inputSha256':prior['original_assemblies']['RoR2.dll'],'outputSha256':prior['original_assemblies']['RoR2.dll'],'fullOriginal':True,'original_assemblies':prior['original_assemblies']}
    else:
        if stage.exists():raise RuntimeError('Prior slice stage remains; inspect first')
        if (WORK/'lab-project/Assets/LabOriginalClosure').exists():raise RuntimeError('Full original closure already staged; do not add duplicate RoR2 assembly')
        command=probe_tool();source=game()/'Risk of Rain 2_Data/Managed/RoR2.dll'
        selected=['RoR2.Trajectory','RoR2.ProcChainMask','RoR2.ProcType']
        process=run(command+['--slice',source,out/'RoR2.dll']+selected,check=False)
        (out/'preparation.stdout').write_bytes(process.stdout);(out/'preparation.stderr').write_bytes(process.stderr)
        if process.returncode:
            write(out/'result.json',{'success':False,'category':'slice-preparation','exit_code':process.returncode})
            raise RuntimeError('Slice preparation failed; full output at '+str(out))
        provenance=json.loads(process.stdout);stage.mkdir();shutil.copy2(out/'RoR2.dll',stage/'RoR2.dll')
    write(out/'slice-provenance.json',provenance)
    resources=stage/'Resources';resources.mkdir()
    shutil.copy2(ROOT/'tools/unity/RoR2SliceProbe.cs',stage/'RoR2SliceProbe.cs')
    write(resources/'RoR2SliceProbe.json',{'attempt':out.name,'inputHash':provenance['inputSha256'],'sliceHash':provenance['outputSha256']})
    (stage/'link.xml').write_text('<linker><assembly fullname="RoR2" preserve="all" /></linker>\n')
    scope='Full unchanged original RoR2 assembly; ten trajectory/proc assertions, not startup or simulation' if full_original else '35 retained method bodies in type-pruned original RoR2 assembly; no EntityStates, full closure, startup or character simulation'
    result={'success':False,'attempt':out.name,'input_id':read(WORK/'inventory/files.json')['input_id'],'scope':scope,'launches':[]}
    write(out/'attempt.json',result);d=Device();had=d.exists()
    try:
        built=build('vulkan',True);result['build']=built
        for name,h in provenance.get('original_assemblies',{'RoR2.dll':provenance['outputSha256']}).items():
            if sha(stage/name)!=h:raise RuntimeError('Assembly changed during build: '+name)
        result['install']=d.install(built['apk']);d.launch();result['sync']=d.sync()
        for index in range(3):
            run_dir=out/('launch-'+str(index+1));run_dir.mkdir()
            start=time.monotonic();runtime=d.launch();pid=runtime['pid']
            # Do not infer 30-second survival from an early success marker.
            while time.monotonic()-start<35:
                if d.sh('pidof',__import__('device').PACKAGE,check=False).strip()!=pid:raise RuntimeError('Slice process died or changed during survival window')
                time.sleep(1)
            paths=read(WORK/'device/runtime.json');report=json.loads(d.sh('cat',paths['persistentDataPath']+'/ror2-slice.json'))
            write(run_dir/'probe.json',report);d.collect('all',run_dir)
            passed=report['success'] and report['assertions']==10 and report['attempt']==out.name and str(report['pid'])==pid and report['sliceHash']==provenance['outputSha256']
            launch={'success':passed,'pid':pid,'survival_seconds':time.monotonic()-start,'evidence':str(run_dir.relative_to(ROOT))};result['launches'].append(launch);write(out/'progress.json',result)
            if not passed:raise RuntimeError('Original slice assertions or launch attribution failed')
        result['success']=True
    except Exception as e:
        result['error']=str(e)
        if 'install' in result:
            try:d.collect('all',out/'failure')
            except Exception as capture:result['capture_error']=str(capture)
    finally:
        if not had and (WORK/'device/installed.json').exists():
            try:result['cleanup']=d.reset()
            except Exception as e:result['cleanup_error']=str(e);result['success']=False
        if result['success']:
            shutil.copytree(stage,out/'stage');shutil.rmtree(stage)
            meta=stage.with_suffix('.meta')
            if meta.exists():meta.unlink()
        write(out/'result.json',result);write(out.parent/'latest.json',{'path':str(out.relative_to(ROOT)),'success':result['success']})
    print(json.dumps({'success':result['success'],'evidence':str(out.relative_to(ROOT)),'error':result.get('error')},indent=2))
    if not result['success']:raise RuntimeError('Original game slice failed; inspect '+str(out))

def original_closure_prepare():
    """Stage original input DLLs for a full-game AOT experiment; no startup adapter."""
    from build import preflight
    preflight()
    stage=WORK/'lab-project/Assets/LabOriginalClosure'
    if stage.exists():raise RuntimeError('Original closure stage already exists; inspect recorded attempt')
    out=WORK/'experiments/original-closure'/now();out.mkdir(parents=True)
    project=WORK/'lab-project';manifest=project/'Packages/manifest.json'
    (out/'packages-before.json').write_bytes(manifest.read_bytes())
    cfg=read(manifest);reconstruction=ROOT/read(WORK/'config/reconstruction.json')['projects'][0]
    cfg['dependencies'].update({k:v for k,v in read(reconstruction/'Packages/manifest.json')['dependencies'].items() if k.startswith('com.unity.modules.')})
    write(manifest,cfg)
    supplied={'Unity.Burst','Unity.Burst.Unsafe','Unity.Collections','Unity.Collections.LowLevel.ILSupport','Unity.Mathematics','UnityEngine.UI','SimpleJSON'}
    source=game()/'Risk of Rain 2_Data/Managed';stage.mkdir();inputs={};export_only=[]
    inventory=read(WORK/'inventory/managed.json')
    for p in sorted((reconstruction/'Assets/Plugins').glob('*.dll')):
        if p.stem in supplied:continue
        original=source/p.name
        if not original.exists():
            consumers=[a['name'] for a in inventory if any(r['name']==p.stem for r in a['references'])]
            if consumers:raise RuntimeError('Missing referenced original input for '+p.name)
            export_only.append(p.name);continue
        shutil.copy2(original,stage/p.name);inputs[p.name]=sha(original)
    (stage/'link.xml').write_text('<linker><assembly fullname="RoR2" preserve="all" /></linker>\n')
    result={'attempt':out.name,'status':'staged; resolve packages/restart isolated editor before build','input_id':read(WORK/'inventory/files.json')['input_id'],'original_assemblies':inputs,'provided_by_packages_or_existing_lab':sorted(supplied),'excluded_export_only_unreferenced':export_only,'scope':'Full original RoR2.dll rooted, dependency set from exported project names but original bytes; no game startup/auth modifications','stage':str(stage),'evidence':str(out.relative_to(ROOT))}
    write(out/'attempt.json',result);write(out.parent/'current.json',{'path':str(out.relative_to(ROOT))})
    print(json.dumps({'staged_original_dlls':len(inputs),'evidence':result['evidence'],'next':'Resolve pinned manifest in isolated editor, then ./dev prototype --action original-closure-build'},indent=2))

def original_closure_build():
    from build import preflight, build
    preflight();out=ROOT/read(WORK/'experiments/original-closure/current.json')['path'];result=read(out/'attempt.json');stage=Path(result['stage'])
    for name,h in result['original_assemblies'].items():
        if sha(stage/name)!=h:raise RuntimeError('Staged original assembly drift: '+name)
    if (out/'result.json').exists():raise RuntimeError('Attempt already terminal; preserve it and create a new attempt')
    logfile=Path(read(WORK/'editor/lab-process.json')['log']);offset=logfile.stat().st_size
    result['success']=False
    try:
        result['build']=build('vulkan',True)
        for name,h in result['original_assemblies'].items():
            if sha(stage/name)!=h:raise RuntimeError('Original assembly changed during import/build: '+name)
        result['post_build_original_hashes_verified']=True
        result['success']=True;result['status']='AOT build passed; not yet installed or launched'
    except Exception as e:result['error']=str(e);result['status']='build failed or incomplete; inspect first failure'
    finally:
        with logfile.open('rb') as f:f.seek(offset);raw=f.read()
        (out/'editor-build.log').write_bytes(raw)
        import re
        errors=[line for line in raw.decode(errors='replace').splitlines() if re.search(r'error CS|IL2CPP error|InvalidOperationException|error:|Exception:',line)]
        write(out/'first-failure.json',{'success':result['success'],'messages':errors[:60],'no_apk_installed':True})
        if (WORK/'lab-build/result.json').exists():shutil.copy2(WORK/'lab-build/result.json',out/'unity-build-result.json')
        write(out/'result.json',result)
    print(json.dumps({'success':result['success'],'evidence':str(out.relative_to(ROOT)),'status':result['status'],'error':result.get('error')},indent=2))
    if not result['success']:raise RuntimeError('Full original closure did not pass; inspect '+str(out))
