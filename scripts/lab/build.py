from common import *
import shutil,time,zipfile,sys

def copy_build_artifact(source, destination):
 # Independent copy-on-write snapshots prevent repeated payloads exhausting host space.
 # Fall back to ordinary copies off APFS; artifact identity is always byte-checked.
 source=Path(source);destination=Path(destination)
 if not source.is_file() or source.is_symlink() or destination.is_symlink():raise RuntimeError('Build artifact paths must be regular files')
 destination.parent.mkdir(parents=True,exist_ok=True)
 cloned=sys.platform=='darwin' and run(['/bin/cp','-c','-p',source,destination],check=False).returncode==0
 if not cloned:shutil.copy2(source,destination)
 source_stat=source.stat();destination_stat=destination.stat()
 if (source_stat.st_dev,source_stat.st_ino)==(destination_stat.st_dev,destination_stat.st_ino) or sha(source)!=sha(destination):raise RuntimeError('Build snapshot independence or hash verification failed')
 return str(destination)

def validate_runtime_support(project, recipe):
 config_path=project/'Assets/LabLoadingScene/Resources/MovementBatchProbe.json'
 if not config_path.exists():return
 config=read(config_path)
 required=config.get('objectiveSupportAssets',[])
 supplied={path.casefold() for path in recipe.get('objectiveSupportAssets',[])}
 missing=[path for path in required if path.casefold() not in supplied]
 if missing:raise RuntimeError('Runtime objective support omitted from build recipe: '+', '.join(missing))
 character={path.casefold() for path in recipe.get('prefabAssets',[])}
 if character & supplied:raise RuntimeError('Runtime objective support has two explicit bundle owners')
 missing_effects=[path for path in config.get('objectiveEffectAssets',[]) if path.casefold() not in character | supplied]
 if missing_effects:raise RuntimeError('Runtime objective effect has no explicit bundle owner: '+', '.join(missing_effects))

def preflight():
 cfg=config();base=game();inv=read(WORK/'inventory/files.json');current={str(p.relative_to(base)):(p.stat().st_size,p.stat().st_mtime_ns) for p in base.rglob('*') if p.is_file()};prior={x['path']:(x['size'],x['mtime_ns']) for x in inv['files']}
 if current!=prior:raise RuntimeError('Input changed: run ./dev inspect, review input-diff and explicitly adopt a new baseline')
 accepted=read(WORK/'config/accepted-input.json') if (WORK/'config/accepted-input.json').exists() else None
 if not accepted or accepted['input_id']!=inv['input_id']:raise RuntimeError('Input not accepted; review inventory before updating work/config/accepted-input.json')
 if shutil.disk_usage(ROOT).free<10*1024**3:raise RuntimeError('Less than 10 GiB host headroom')
 if (ROOT/'smoke/ProjectSettings/ProjectVersion.txt').read_text().find('2021.3.33f1')<0:raise RuntimeError('Unity version pin changed')
 tracked=run(['git','ls-files','-z'],check=True).stdout.decode().split('\0');bad=[p for p in tracked if p.startswith(('work/','build/','logs/','screenshots/')) or Path(p).suffix.lower() in ['.dll','.exe','.so','.apk','.aab','.bnk','.wem','.bundle','.keystore','.jks']]
 if bad:raise RuntimeError('Restricted files tracked: '+str(bad))
 from device import Device
 storage=Device().storage()
 result={'success':True,'input_id':inv['input_id'],'host_free_bytes':shutil.disk_usage(ROOT).free,'storage':storage,'scope':'lab build; does not certify full game or semantic patches'};write(WORK/'preflight.json',result);return result

def editor(target='lab',action='inspect'):
 if action=='open':
  project=WORK/'lab-project' if target=='lab' else ROOT/'smoke' if target=='smoke' else ROOT/read(WORK/'config/reconstruction.json')['projects'][0]
  if not project.is_dir():raise RuntimeError('Project does not exist: '+str(project))
  commands=run(['/bin/ps','-axo','command']).stdout.decode().splitlines()
  if any(c.startswith(os.environ['UNITY_EDITOR']+' ') and ' -projectPath '+str(project)+' ' in c for c in commands):return 'Editor already open; inspect MCP connectivity with ./dev editor --target '+target
  env=os.environ.copy();env.update({'ANDROID_SDK_HOME':str(ROOT/'.local/android-user'),'ANDROID_USER_HOME':str(ROOT/'.local/android-user/.android'),'GRADLE_USER_HOME':str(ROOT/'.local/gradle')})
  log=WORK/(target+'-editor-'+now()+'.log')
  proc=subprocess.Popen([os.environ['UNITY_EDITOR'],'-batchmode','-projectPath',str(project),'-executeMethod','BootstrapMcp.Connect','-logFile',str(log)]+(['-buildTarget','Android'] if target=='lab' else []),cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
  write(WORK/'editor'/(target+'-process.json'),{'pid':proc.pid,'project':str(project),'log':str(log)})
  return json.dumps({'started':True,'pid':proc.pid,'log':str(log),'next':'Wait for import/MCP connection, then ./dev editor --target '+target})
 if action=='minimal-build':preflight()
 return run([ROOT/'.local/tools/unity-mcp/Server/.venv/bin/python',ROOT/'scripts/lab/editor.py',target,action],timeout=200).stdout.decode()

def build(api='gles',force=False):
 if api not in ['gles','vulkan','lab']:raise RuntimeError('Build target must be gles or vulkan')
 if api=='lab':api='gles'
 preflight()
 project=WORK/'lab-project'
 recipe=WORK/'scene-probe-build.json'
 if recipe.exists():validate_runtime_support(project,read(recipe))
 # Copy changed tool-owned sources only. Never reset project settings during an incremental build.
 shutil.copytree(ROOT/'android/Assets',project/'Assets',dirs_exist_ok=True)
 inputs={str(p.relative_to(project)):sha(p) for sub in ['Assets','Packages','ProjectSettings'] for p in sorted((project/sub).rglob('*')) if p.is_file() and p.suffix!='.unity' and p.name!='Lab.unity.meta'}
 key=digest({'inputs':inputs,'api':api,'editor':'2021.3.33f1','backend':'IL2CPP-ARM64','tool':sha(ROOT/'scripts/lab/build.py')})
 dest=WORK/'build-cache'/key;receipt=dest/'result.json'
 if receipt.exists() and not force:
  r=read(receipt)
  if r.get('success') and r.get('errors',0)==0 and Path(r['apk']).exists() and sha(r['apk'])==r['apk_sha256']:
   for name,h in r.get('payload',{}).items():
    source=dest/'payload'/name
    if not source.is_file() or sha(source)!=h:raise RuntimeError('Cached payload is missing or changed: '+name)
    copy_build_artifact(source,WORK/'generated-android-data'/name)
   write(WORK/'config/current-build.json',r);print(json.dumps({'cached':True,**r},indent=2));return r
 (WORK/'graphics-api.txt').write_text(api);result=WORK/'lab-build/result.json'
 if result.exists():result.rename(result.with_name('previous-'+now()+'.json'))
 request_id=now();write(WORK/'build-request.json',{'request_id':request_id,'api':api})
 print(editor('lab','refresh'),flush=True)
 print(editor('lab','build'),flush=True)
 dispatch_deadline=time.monotonic()+120;deadline=time.monotonic()+1200
 while time.monotonic()<deadline:
  if result.exists():
   if read(result).get('request_id')!=request_id:raise RuntimeError('Terminal build receipt belongs to a different request')
   break
  if time.monotonic()>dispatch_deadline and (not (WORK/'lab-build/started.json').exists() or read(WORK/'lab-build/started.json').get('request_id')!=request_id):raise RuntimeError('Queued build never started; inspect editor dispatch evidence')
  time.sleep(2)
 else:raise RuntimeError('Build timeout; inspect work/lab-editor.log; no cache stamp written')
 r=read(result)
 if not r['success'] or r.get('errors',0)>0:raise RuntimeError(r['result']+'; build errors='+str(r.get('errors',0)))
 inputs={str(p.relative_to(project)):sha(p) for sub in ['Assets','Packages','ProjectSettings'] for p in sorted((project/sub).rglob('*')) if p.is_file() and p.suffix!='.unity' and p.name!='Lab.unity.meta'}
 key=digest({'inputs':inputs,'api':api,'editor':'2021.3.33f1','backend':'IL2CPP-ARM64','tool':sha(ROOT/'scripts/lab/build.py')})
 dest=WORK/'build-cache'/key;receipt=dest/'result.json'
 dest.mkdir(parents=True,exist_ok=True);apk=dest/Path(r['apk']).name;copy_build_artifact(r['apk'],apk)
 r.update({'apk':str(apk),'apk_sha256':sha(apk),'key':key,'graphics_api':api,'input_id':read(WORK/'inventory/files.json')['input_id']})
 payload=dest/'payload';shutil.copytree(WORK/'generated-android-data',payload,dirs_exist_ok=True,copy_function=copy_build_artifact)
 r['payload']={p.name:sha(p) for p in payload.glob('*') if p.is_file()}
 write(receipt,r);write(WORK/'config/current-build.json',r);print(json.dumps(r,indent=2));return r
