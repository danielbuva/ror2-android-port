from common import *
import time,re,shlex,zipfile
PACKAGE='dev.ror2lab.arm64'
ADB='/opt/homebrew/bin/adb'
class Device:
 def __init__(self):
  serial=config()['device_serial'];lines=run([ADB,'devices']).stdout.decode().splitlines()[1:]
  if [serial,'device'] not in [l.split()[:2] for l in lines]:raise RuntimeError('Configured device is not connected and authorized: '+serial)
  self.base=[ADB,'-s',serial];self.serial=serial
 def cmd(self,*args,check=True,timeout=120):return run(self.base+list(args),check=check,timeout=timeout).stdout.decode(errors='replace').strip()
 def sh(self,*args,check=True):return self.cmd('shell',shlex.join(str(a) for a in args),check=check)
 def exists(self):return ('package:'+PACKAGE) in self.sh('pm','list','packages',PACKAGE).splitlines()
 def owned(self):
  receipt=WORK/'device/installed.json'
  if not receipt.exists():raise RuntimeError('No lab ownership receipt; refusing to modify an existing package')
  r=read(receipt)
  if r['serial']!=self.serial or r['package']!=PACKAGE or self.sh('pm','path',PACKAGE)!=r['package_path']:raise RuntimeError('Package placement/ownership changed; inspect before modifying')
  return r
 def storage(self):
  lines=[x.split() for x in self.sh('sm','list-volumes','all').splitlines() if x.startswith('private:') and ' mounted ' in x]
  if len(lines)!=1 or not re.fullmatch('[a-fA-F0-9-]+',lines[0][2]):raise RuntimeError('Expected exactly one mounted adopted private volume')
  uuid=lines[0][2]
  def df(path):
   text=self.sh('df','-k',path);parts=text.splitlines()[-1].split();return {'path':path,'total_bytes':int(parts[1])*1024,'free_bytes':int(parts[3])*1024,'raw':text}
  result={'serial':self.serial,'uuid':uuid,'internal':df('/data'),'adopted':df('/mnt/expand/'+uuid),'shared':df('/sdcard'),'install_location':self.sh('pm','get-install-location')}
  write(WORK/'device/storage.json',result);return result
 def install(self,apk):
  if self.exists():self.owned()
  storage=self.storage();apk=Path(apk)
  with zipfile.ZipFile(apk) as z:
   abis={n.split('/')[1] for n in z.namelist() if n.startswith('lib/') and n.endswith('.so')};native=sum(i.file_size for i in z.infolist() if i.filename.startswith('lib/'))
  if abis!={'arm64-v8a'}:raise RuntimeError('APK must contain only arm64-v8a; found '+str(abis))
  reserve=config().get('internal_reserve_mib',1024)*1024**2;estimate=apk.stat().st_size*3+native
  if storage['internal']['free_bytes']<reserve+estimate:raise RuntimeError('Insufficient internal installation scratch headroom; do not move/remove games')
  if storage['adopted']['free_bytes']<estimate+reserve:raise RuntimeError('Insufficient adopted storage headroom')
  t=time.monotonic();output=self.cmd('install','-r','--force-uuid',storage['uuid'],str(apk),timeout=240)
  r={'serial':self.serial,'package':PACKAGE,'apk':str(apk),'apk_sha256':sha(apk),'package_path':self.sh('pm','path',PACKAGE),'details':self.sh('dumpsys','package',PACKAGE),'seconds':time.monotonic()-t,'install_output':output,'storage':storage}
  write(WORK/'device/installed.json',r)
  if '/mnt/expand/'+storage['uuid']+'/' not in r['package_path']:raise RuntimeError('Placement verification failed; lab receipt saved, inspect before next action')
  return r
 def launch(self):
  self.owned();self.sh('am','force-stop',PACKAGE);start=self.sh('date','+%s.%N')
  launch=self.sh('am','start','-W','-n',PACKAGE+'/com.unity3d.player.UnityPlayerActivity');deadline=time.monotonic()+45;logs='';pid=''
  while time.monotonic()<deadline:
   pid=self.sh('pidof',PACKAGE,check=False).strip()
   if pid:
    logs=self.cmd('logcat','-d','--pid='+pid,'-v','epoch','Unity:I','AndroidRuntime:E','*:S')
    if 'LAB_READY' in logs:break
   time.sleep(1)
  snapshots=[]
  for line in logs.splitlines():
   if 'LAB_SNAPSHOT {' in line:
    try:snapshots.append(json.loads(line.split('LAB_SNAPSHOT ',1)[1]))
    except ValueError:pass
  if not snapshots:
   match=re.search(r'"persistentDataPath":"([^"]+)"',logs)
   if match:
    path=match.group(1)
    if not path.endswith('/Android/data/'+PACKAGE+'/files'):raise RuntimeError('Unexpected diagnostic path')
    snapshots.append(json.loads(self.sh('cat',path+'/snapshot.json')))
  if snapshots:write(WORK/'device/runtime.json',snapshots[-1])
  result={'launch':launch,'pid':pid,'device_start':start,'checkpoint':'LAB_READY' in logs,'managed_assembly':'LAB_MANAGED_ASSEMBLY_OK' in logs,'geometry':'LAB_GEOMETRY_OK' in logs,'log':logs}
  write(WORK/'device/last-run.json',result)
  if not result['checkpoint']:raise RuntimeError('Runtime checkpoint failed; inspect work/device/last-run.json and ./dev crash')
  return result
 def sync(self):
  self.owned();runtime=read(WORK/'device/runtime.json');path=runtime['persistentDataPath'];storage=self.storage()
  if not path.endswith('/Android/data/'+PACKAGE+'/files'):raise RuntimeError('Unexpected runtime content path; inspect storage before extending sync policy')
  dest=path+'/payload';self.sh('mkdir','-p',dest);files=list((WORK/'generated-android-data').glob('*'));manifest=[]
  for p in sorted(files):
   if not p.is_file() or p.suffix=='.manifest':continue
   h=sha(p);remote=dest+'/'+p.name
   if not re.fullmatch('[A-Za-z0-9_.-]+',p.name):raise RuntimeError('Unsafe payload filename')
   existing=self.sh('sha256sum',remote,check=False).split()
   changed=not existing or existing[0]!=h
   if changed:
    if storage['adopted']['free_bytes']<p.stat().st_size*2+1024**3:raise RuntimeError('Payload exceeds adopted free space')
    self.cmd('push',str(p),remote+'.partial',timeout=300)
    got=self.sh('sha256sum',remote+'.partial').split()[0]
    if got!=h:raise RuntimeError('Transferred payload hash mismatch')
    self.sh('mv',remote+'.partial',remote)
   manifest.append({'name':p.name,'sha256':h,'bytes':p.stat().st_size,'transferred':changed})
  result={'runtime_path':path,'backing_df':self.sh('df','-k',path),'files':manifest};write(WORK/'device/sync.json',result);return result
 def collect(self,kind,out):
  out.mkdir(parents=True,exist_ok=True);result={}
  if kind in ['all','logs']:
   pid=self.sh('pidof',PACKAGE,check=False).strip();logs=self.cmd('logcat','-d',*(['--pid='+pid] if pid else []),'-v','threadtime','Unity:I','AndroidRuntime:E','*:S');(out/'unity.log').write_text(logs)
  if kind in ['all','crash']:
   (out/'crash.log').write_text(self.cmd('logcat','-b','crash','-d','-v','threadtime'))
   (out/'exit-info.txt').write_text(self.sh('dumpsys','activity','exit-info',PACKAGE,check=False))
   (out/'tombstone-access.txt').write_text(self.sh('ls','/data/tombstones',check=False) or 'Not accessible on this non-root device')
  if kind in ['all','screenshot']:
   data=run(self.base+['exec-out','screencap','-p']).stdout
   if not data.startswith(b'\x89PNG\r\n\x1a\n'):raise RuntimeError('Invalid screenshot')
   (out/'screenshot.png').write_bytes(data)
  if kind in ['all','perf']:
   for name,args in {'memory':['dumpsys','meminfo',PACKAGE],'gfxinfo':['dumpsys','gfxinfo',PACKAGE],'thermal':['dumpsys','thermalservice'],'cpu':['dumpsys','cpuinfo']}.items():(out/(name+'.txt')).write_text(self.sh(*args,check=False))
   if (WORK/'device/runtime.json').exists():
    path=read(WORK/'device/runtime.json')['persistentDataPath']
    for name in ['snapshot.json','exceptions.jsonl']:
     text=self.sh('cat',path+'/'+name,check=False)
     if text:(out/name).write_text(text)
    (out/'private-path.txt').write_text(self.sh('run-as',PACKAGE,'pwd',check=False))
    (out/'native-maps.txt').write_text(self.sh('run-as',PACKAGE,'cat','/proc/'+self.sh('pidof',PACKAGE,check=False).strip()+'/maps',check=False))
  return {'artifacts':str(out.relative_to(ROOT))}
 def reset(self):
  if not self.exists():return {'removed':False,'reason':'package absent'}
  self.owned();result=self.cmd('uninstall',PACKAGE);(WORK/'device/installed.json').unlink();return {'uninstall':result,'removed':not self.exists()}

def smoke(apk):
 d=Device();out=WORK/'runs'/(now()+'-'+sha(apk)[:12]);out.mkdir(parents=True);result={'success':False,'apk_sha256':sha(apk),'run_id':out.name,'started':now()};had_package=d.exists()
 try:
  result['install']=d.install(apk);d.launch();result['sync']=d.sync();result['runtime']=d.launch();time.sleep(3);d.collect('all',out)
  runtime=result['runtime'];result['success']=runtime['checkpoint'] and runtime['managed_assembly'] and runtime['geometry'];result['graphics_gate']='G2' if runtime['geometry'] else 'G1';result['failure_class']=None if result['success'] else 'runtime-checkpoint'
 except Exception as e:
  result['error']=str(e);result['failure_class']='install-storage' if 'storage' in str(e).lower() else 'first-failure';
  try:
   if 'install' in result:d.collect('all',out)
  except Exception as collection_error:result['collection_error']=str(collection_error)
 finally:
  # Only remove a package first installed by this smoke transaction.
  if not had_package and (WORK/'device/installed.json').exists():
   try:result['cleanup']=d.reset()
   except Exception as e:result['cleanup_error']=str(e);result['success']=False
  write(out/'result.json',result);write(WORK/'runs/latest.json',{'path':str(out.relative_to(ROOT)),'success':result['success']})
 print(json.dumps({'success':result['success'],'artifacts':str(out.relative_to(ROOT)),'error':result.get('error')},indent=2))
 if not result['success']:raise RuntimeError('Smoke failed: '+str(out))
