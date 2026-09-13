from common import *
import re,collections,xml.etree.ElementTree as ET,struct

def recompile():
 src=next(x for x in read(WORK/'inventory/decompilation.json') if x['assembly']=='RoR2.dll');folder=ROOT/src['output'];out=WORK/'experiments/recompile';out.mkdir(parents=True,exist_ok=True);managed=game()/'Risk of Rain 2_Data/Managed';results=[]
 compilers=[('net10-csharp14',[Path.home()/'.local/share/dotnet/dotnet',Path.home()/'.local/share/dotnet/sdk/10.0.401/Roslyn/bincore/csc.dll'],'14'),('unity-csharp9',[Path('/Applications/Unity/Hub/Editor/2021.3.33f1/Unity.app/Contents/MonoBleedingEdge/bin/mono'),Path('/Applications/Unity/Hub/Editor/2021.3.33f1/Unity.app/Contents/MonoBleedingEdge/lib/mono/msbuild/Current/bin/Roslyn/csc.exe')],'9')]
 for label,cmd,lang in compilers:
  args=['/noconfig','/nostdlib+','/target:library','/unsafe+','/langversion:'+lang,'/out:"'+str(out/(label+'.dll'))+'"']+['/reference:"'+str(p)+'"' for p in sorted(managed.glob('*.dll')) if p.name!='RoR2.dll']+['"'+str(p)+'"' for p in sorted(folder.rglob('*.cs'))]
  rsp=out/(label+'.rsp');rsp.write_text('\n'.join(args));p=run(cmd+['@'+str(rsp)],timeout=180,check=False);log=(p.stdout+p.stderr).decode(errors='replace');(out/(label+'.log')).write_text(log)
  errors=list(dict.fromkeys(x for x in log.splitlines() if re.search(r'error CS\d+',x)));r={'compiler':label,'exit_code':p.returncode,'unique_errors':len(errors),'categories':dict(collections.Counter(re.search(r'error (CS\d+)',x).group(1) for x in errors)),'log':str((out/(label+'.log')).relative_to(ROOT))};results.append(r)
 write(out/'result.json',results);print(json.dumps(results,indent=2))

def middleware():
 import pefile
 base=game();p=base/'Risk of Rain 2_Data/Plugins/x86_64/AkSoundEngine.dll';pe=pefile.PE(str(p));version={}
 for sym in pe.DIRECTORY_ENTRY_EXPORT.symbols:
  if sym.name in [b'CSharp_GetMajorMinorVersion',b'CSharp_GetSubminorBuildVersion']:
   address=sym.address;code=pe.get_data(address,16)
   for _ in range(4):
    if code[:1]!=b'\xe9':break
    address=address+5+struct.unpack('<i',code[1:5])[0];code=pe.get_data(address,16)
   if code[:1]==b'\xb8' and code[5:6]==b'\xc3':
    n=struct.unpack('<I',code[1:5])[0];version[sym.name.decode()]={'rva':hex(sym.address),'bytes':code[:6].hex(),'hi':n>>16,'lo':n&65535}
 pe.close()
 xml=base/'Risk of Rain 2_Data/StreamingAssets/Audio/GeneratedSoundBanks/Windows/SoundbanksInfo.xml';banks=ET.parse(xml).getroot().attrib
 major=version.get('CSharp_GetMajorMinorVersion',{});minor=version.get('CSharp_GetSubminorBuildVersion',{})
 result={'wwise':{'native_version':'.'.join(str(x) for x in [major.get('hi'),major.get('lo'),minor.get('hi'),minor.get('lo')]),'evidence':version,'banks':banks,'native_sha256':sha(p)},'rewired':{'version':'1.1.47.0.U2021','evidence':'decompiled Rewired_Core/Rewired/ReInput.cs programVersion getter'}}
 write(WORK/'inventory/middleware.json',result);print(json.dumps(result,indent=2))

def reconstruction_report():
 cfg=read(WORK/'config/reconstruction.json');project=ROOT/cfg['projects'][0];shaders=list(project.rglob('*.shader'));patterns=collections.Counter();samples=[]
 for f in shaders:
  t=f.read_text(errors='replace');stub='DummyShader' in t or 'stub' in t.lower() or 'AssetRipper' in t
  patterns['files']+=1;patterns['contains_shaderlab']+=int('SubShader' in t);patterns['contains_hlsl']+=int('CGPROGRAM' in t or 'HLSLPROGRAM' in t);patterns['mentions_dummy_stub_or_assetripper']+=int(stub)
  if 'Hopoo Games/Deferred/Standard"' in t:samples.append({'file':str(f.relative_to(ROOT)),'bytes':f.stat().st_size,'stub_marker':stub})
 result={'project':str(project.relative_to(ROOT)),'cs_files':len(list(project.rglob('*.cs'))),'preserved_dlls':len(list(project.rglob('*.dll'))),'scenes':len(list(project.rglob('*.unity'))),'shader_recovery':dict(patterns),'standard_shader_samples':samples}
 write(WORK/'inventory/reconstruction.json',result);print(json.dumps(result,indent=2))

def references():
 cfg=read(WORK/'config/reconstruction.json');project=ROOT/cfg['projects'][0];known=set();missing={};files=0;refs=0
 for p in (project/'Assets').rglob('*.meta'):
  m=re.search(r'^guid:\s*([a-f0-9]{32})',p.read_text(errors='replace'),re.M)
  if m:known.add(m.group(1))
 for p in (project/'Assets').rglob('*'):
  if not p.is_file() or p.suffix not in ['.unity','.prefab','.asset','.mat','.controller','.anim']:continue
  with p.open('rb') as f:
   if not f.read(10).startswith(b'%YAML'):continue
  files+=1
  for guid in re.findall(r'guid:\s*([a-f0-9]{32})',p.read_text(errors='replace')):
   refs+=1
   if guid in known or guid.startswith('0000000000000000'):continue
   row=missing.setdefault(guid,{'count':0,'examples':[]});row['count']+=1
   if len(row['examples'])<3:row['examples'].append(str(p.relative_to(project)))
 result={'scope':'Assets YAML external GUIDs only; local fileID, package and runtime bundle references need separate resolution','yaml_files':files,'references':refs,'known_asset_guids':len(known),'missing_guid_count':len(missing),'missing':missing};write(WORK/'inventory/serialized-references.json',result);print(json.dumps({k:v for k,v in result.items() if k!='missing'},indent=2))
