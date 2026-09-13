#!/usr/bin/env python3
import json, subprocess, sys, datetime
from pathlib import Path
adb='/opt/homebrew/bin/adb'
def run(*args):
    p=subprocess.run([adb,*args],text=True,capture_output=True,timeout=30)
    if p.returncode: raise RuntimeError(p.stderr.strip() or p.stdout.strip())
    return p.stdout.strip()
devices=[l.split()[0] for l in run('devices').splitlines()[1:] if len(l.split())>=2 and l.split()[1]=='device']
if len(devices)!=1: sys.exit('Connect exactly one authorized Android device.')
serial=devices[0]
def sh(cmd): return run('-s',serial,'shell',cmd)
props={k:sh('getprop '+k) for k in ['ro.product.model','ro.product.manufacturer','ro.build.version.release','ro.build.version.sdk','ro.product.cpu.abilist','ro.build.fingerprint','ro.soc.model']}
volumes=sh('sm list-volumes all')
adopted=[]
for line in volumes.splitlines():
    parts=line.split()
    if parts[0].startswith('private:') and len(parts)==3 and parts[1]=='mounted':
        uuid=parts[2]; path='/mnt/expand/'+uuid
        fields=sh('df -k '+path).splitlines()[-1].split()
        adopted.append({'id':parts[0],'uuid':uuid,'path':path,'total_kib':int(fields[1]),'free_kib':int(fields[3])})
datafields=sh('df -k /data').splitlines()[-1].split()
sf=sh('dumpsys SurfaceFlinger')
profile={'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'serial':serial,'properties':props,'gpu':[l.strip() for l in sf.splitlines() if 'GLES:' in l],'memory':sh('head -5 /proc/meminfo'),'display_size':sh('wm size'),'display_modes':[l.strip() for l in sh('dumpsys display').splitlines() if 'supportedModes' in l][:1],'vulkan_features':[l for l in sh('pm list features').splitlines() if 'vulkan' in l],'install_location':sh('pm get-install-location'),'volumes':volumes,'disks':sh('sm list-disks'),'physical_internal':{'total_kib':int(datafields[1]),'free_kib':int(datafields[3])},'adopted':adopted,'adopted_package_count':sum('/mnt/expand/' in l for l in sh('pm list packages -f').splitlines())}
path=Path(__file__).resolve().parents[1]/'environment/device-profile.json'
path.write_text(json.dumps(profile,indent=2)+'\n')
print(json.dumps(profile,indent=2))
