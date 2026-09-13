#!/usr/bin/env python3
"""Install only this disposable smoke app; capture evidence; uninstall in finally."""
import datetime, hashlib, json, subprocess, time, sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]; out=root/'environment'; adb='/opt/homebrew/bin/adb'; package='dev.localbootstrap.arm64smoke'
def cmd(args,timeout=120):
    p=subprocess.run(args,capture_output=True,timeout=timeout)
    if p.returncode: raise RuntimeError((p.stdout+p.stderr).decode(errors='replace'))
    return p.stdout.decode(errors='replace').strip()
devices=[l.split()[0] for l in cmd([adb,'devices']).splitlines()[1:] if len(l.split())>1 and l.split()[1]=='device']
if len(devices)!=1:raise RuntimeError('Connect exactly one authorized device')
base=[adb,'-s',devices[0]]
def sh(s):return cmd(base+['shell',s])
def package_exists():return ('package:'+package) in sh('pm list packages '+package).splitlines()
if package_exists():raise RuntimeError('Smoke package already exists: inspect its ownership before replacing/removing it.')
apk=root/'builds/bootstrap-arm64.apk'
result={'success':False,'time':datetime.datetime.now(datetime.timezone.utc).isoformat(),'serial':devices[0],'package':package,'apk_sha256':hashlib.sha256(apk.read_bytes()).hexdigest()}
install_args=[]
if '--adopted' in sys.argv:
    volumes=[l.split() for l in sh('sm list-volumes all').splitlines() if l.startswith('private:') and ' mounted ' in l]
    if len(volumes)!=1:raise RuntimeError('Expected exactly one mounted adopted private volume')
    result['requested_volume_uuid']=volumes[0][2]
    install_args=['--force-uuid',volumes[0][2]]
installed=False
try:
    result['install']=cmd(base+['install','-r']+install_args+[str(apk)]); installed=True
    result['package_path']=sh('pm path '+package)
    result['package_details']='\n'.join(l.strip() for l in sh('dumpsys package '+package).splitlines() if any(k in l for k in ['codePath=','volumeUuid=','primaryCpuAbi=','installLocation=']))
    result['launch']=sh('am start -W -n '+package+'/com.unity3d.player.UnityPlayerActivity')
    time.sleep(8)
    pid=sh('pidof '+package).split()[0]
    logs=cmd(base+['logcat','-d','--pid='+pid,'-v','threadtime','Unity:I','AndroidRuntime:E','*:S'])
    (out/'smoke-logcat.txt').write_text(logs+'\n')
    result['marker_found']='ROR2_BOOTSTRAP_ARM64_OK' in logs
    result['pid']=pid
    if not result['marker_found']:raise RuntimeError('Unity bootstrap marker missing; screenshot skipped')
    screenshot=subprocess.run(base+['exec-out','screencap','-p'],capture_output=True,check=True,timeout=30).stdout
    if not screenshot.startswith(b'\x89PNG\r\n\x1a\n'):raise RuntimeError('Invalid screenshot')
    (out/'smoke-screenshot.png').write_bytes(screenshot)
    result['screenshot']='environment/smoke-screenshot.png'
    result['success']=result['marker_found'] and 'arm64-v8a' in result['package_details']
    if install_args:result['success']=result['success'] and '/mnt/expand/'+result['requested_volume_uuid']+'/' in result['package_path']
finally:
    if installed:
        sh('am force-stop '+package)
        result['uninstall']=cmd(base+['uninstall',package])
        result['removed']=not package_exists()
    (out/'smoke-result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
if not result['success']:raise SystemExit(1)
