from common import *
import re,struct,collections

def inspect(full=False):
 base=game(); out=WORK/'inventory'; out.mkdir(parents=True,exist_ok=True)
 previous=read(out/'files.json') if (out/'files.json').exists() else {}
 old={x['path']:x for x in previous.get('files',[])}; files=[]
 for p in sorted(base.rglob('*')):
  if not p.is_file(): continue
  rel=str(p.relative_to(base)); s=p.stat(); x={'path':rel,'size':s.st_size,'mtime_ns':s.st_mtime_ns}
  x['sha256']=old[rel]['sha256'] if not full and rel in old and all(old[rel].get(k)==x[k] for k in ['size','mtime_ns']) else sha(p)
  with p.open('rb') as f: head=f.read(256)
  if head.startswith(b'UnityFS\0'): x['bundle_header']=head[:100].decode('ascii',errors='replace'); x['category']='bundle'
  elif p.suffix.lower() in ['.dll','.exe']: x['category']='managed' if '/Managed/' in rel else 'native'
  elif p.suffix.lower()=='.bnk': x['category']='soundbank'
  else: x['category']='data'
  files.append(x)
 identity=digest([(x['path'],x['sha256']) for x in files]); gg=base/'Risk of Rain 2_Data/globalgamemanagers'
 unity=re.findall(rb'20\d\d\.\d+\.\d+[abfp]\d+',gg.read_bytes()[:512])
 # Read only build identifiers from app manifest: never copy account/user fields.
 manifest=base.parent.parent/'appmanifest_632360.acf'; steam={}
 if manifest.exists():
  t=manifest.read_text(); steam={k:(re.search(r'"'+k+r'"\s+"([^"]+)"',t).group(1) if re.search(r'"'+k+r'"\s+"([^"]+)"',t) else None) for k in ['appid','buildid','LastUpdated','installdir']}
 report={'schema':1,'captured_at':now(),'input_id':identity,'unity_versions':[x.decode() for x in unity],'steam':steam,'files':files,'total_bytes':sum(x['size'] for x in files),'hash_mode':'full' if full else 'size/mtime cached SHA256'}
 if previous and previous.get('input_id')!=identity: write(out/'history'/f"{previous['input_id']}.json",previous)
 write(out/'files.json',report)
 changes={'game_build_changed':bool(previous) and previous.get('steam',{}).get('buildid')!=steam.get('buildid'),'old_build':previous.get('steam',{}),'new_build':steam,'old_input':previous.get('input_id'),'new_input':identity,'added':[x['path'] for x in files if x['path'] not in old],'removed':sorted(set(old)-{x['path'] for x in files}),'changed':[{'path':x['path'],'category':x['category']} for x in files if x['path'] in old and x['sha256']!=old[x['path']]['sha256']]}
 write(out/'input-diff.json',changes)
 managed=base/'Risk of Rain 2_Data/Managed'; key=digest({'files':[(x['path'],x['sha256']) for x in files if x['category']=='managed'],'tool':sha(ROOT/'tools/ManagedInventory/Program.cs')})
 if not (out/'managed-stamp.json').exists() or read(out/'managed-stamp.json')['key']!=key:
  run(['dotnet','build',ROOT/'tools/ManagedInventory','-o',ROOT/'.local/managed-inventory'],timeout=120)
  result=run(['dotnet',ROOT/'.local/managed-inventory/ManagedInventory.dll',managed],timeout=180)
  parsed=json.loads(result.stdout)
  if (out/'managed.json').exists():
   prior=read(out/'managed.json'); write(out/'managed-previous.json',prior)
   surfaces=lambda rows:{x['file']:digest(x.get('types',[])) for x in rows}
   a,b=surfaces(prior),surfaces(parsed); write(out/'surface-diff.json',{'changed':[k for k in b if a.get(k)!=b[k]],'removed':sorted(set(a)-set(b))})
  write(out/'managed.json',parsed); write(out/'managed-stamp.json',{'key':key})
 import pefile
 natives=[]
 for x in files:
  if x['category']!='native':continue
  try:
   pe=pefile.PE(str(base/x['path']),fast_load=False)
   info={'path':x['path'],'machine':hex(pe.FILE_HEADER.Machine),'architecture':{0x8664:'x86_64',0x14c:'x86',0xaa64:'arm64'}.get(pe.FILE_HEADER.Machine,'unknown'),'imports':[v.dll.decode(errors='replace') for v in getattr(pe,'DIRECTORY_ENTRY_IMPORT',[])],'versions':{}}
   for group in getattr(pe,'FileInfo',[]):
    for obj in group:
     for table in getattr(obj,'StringTable',[]):info['versions'].update({k.decode(errors='replace'):v.decode(errors='replace') for k,v in table.entries.items()})
   natives.append(info);pe.close()
  except Exception as e:natives.append({'path':x['path'],'error':str(e)})
 write(out/'native.json',natives)
 assemblies=read(out/'managed.json'); names={x.get('name') for x in assemblies}; seams={}
 patterns={'windows':r'Microsoft.Win32|Windows|DirectInput|XInput|Registry','reflection_emit':r'Reflection.Emit|DynamicMethod|AssemblyBuilder','reflection':r'System.Reflection|GetType|GetMethod|Activator','networking':r'Network|Steam|EOS|PlayFab|Party','audio':r'AkSound|Wwise','input':r'Rewired','paths':r'Path|Directory|File|persistentDataPath|streamingAssetsPath'}
 for a in assemblies:
  seams[a['file']]={'unresolved_references':[r for r in a.get('references',[]) if r['name'] not in names],**{k:[s for s in a.get('memberReferences',[]) if re.search(v,s)] for k,v in patterns.items()}}
 write(out/'seams.json',seams)
 summary={'input_id':identity,'files':len(files),'bytes':report['total_bytes'],'unity':report['unity_versions'],'steam':steam,'managed_assemblies':len(assemblies),'types':sum(len(x.get('types',[])) for x in assemblies),'native_binaries':len(natives),'categories':dict(collections.Counter(x['category'] for x in files))}
 write(out/'summary.json',summary);print(json.dumps(summary,indent=2))
