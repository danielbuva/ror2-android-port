"""Bounded metadata attribution for the recorded J09 failure, without running input code."""
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
