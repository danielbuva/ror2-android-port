from common import *
from device import Device

def lifecycle():
 d=Device();out=WORK/'experiments/storage-lifecycle';out.mkdir(parents=True,exist_ok=True)
 if d.exists():raise RuntimeError('Lifecycle experiment requires absent disposable package')
 r={'success':False}
 try:
  apk=read(WORK/'config/current-build.json')['apk'];r['first_install']=d.install(apk);d.launch();r['first_sync']=d.sync();r['second_sync']=d.sync();r['update_install']=d.install(apk);r['after_update_sync']=d.sync();r['update_runtime']=d.launch()
  r['success']=all(not x['transferred'] for x in r['second_sync']['files']) and all(not x['transferred'] for x in r['after_update_sync']['files']) and r['update_runtime']['geometry']
 finally:
  if (WORK/'device/installed.json').exists():r['cleanup']=d.reset()
  write(out/'result.json',r)
 print(json.dumps({'success':r['success'],'evidence':str(out.relative_to(ROOT))},indent=2))
 if not r['success']:raise RuntimeError('Storage lifecycle checkpoint failed')
