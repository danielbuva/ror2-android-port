#!/usr/bin/env python3
import json, os, shutil, subprocess, sys, datetime
from pathlib import Path
root=Path(__file__).resolve().parents[1]
checks=[]
def check(name,ok,detail): checks.append({'name':name,'ok':bool(ok),'detail':detail})
def run(args,timeout=20):
    try:
        r=subprocess.run(args,capture_output=True,text=True,timeout=timeout)
        return r.returncode==0,(r.stdout+r.stderr).strip()
    except (OSError,subprocess.TimeoutExpired) as e:return False,str(e)
for tool in ['git','gh','jq','rg','fd','curl','wget','python3','uv','dotnet','cmake','ninja','pkg-config','7zz','magick','ffmpeg','scrcpy','adb']:
    p=shutil.which(tool);check(tool,p,p or 'Missing')
ok,out=run(['xcode-select','-p']); check('Command Line Tools',ok,out)
unity=Path(os.environ['UNITY_EDITOR']); check('Unity editor',unity.is_file(),str(unity))
plist=unity.parent.parent/'Info.plist'
if plist.exists():
    import plistlib
    v=plistlib.loads(plist.read_bytes()).get('CFBundleVersion','unknown')
    check('Unity exact version',v=='2021.3.33f1',v)
for name,path in [('Android SDK',Path(os.environ['ANDROID_HOME'])/'platforms/android-30/android.jar'),('Android NDK',Path(os.environ['ANDROID_NDK_ROOT'])/'source.properties'),('Unity JDK',Path(os.environ['JAVA_HOME'])/'bin/java'),('Android module',Path(os.environ['UNITY_ANDROID_ROOT'])/'UnityEditor.Android.Extensions.dll')]:
    check(name,path.exists(),str(path))
for name,cmd in [('ilspycmd',[str(root/'scripts/ilspycmd'),'--version']),('AssetRipper',[str(root/'scripts/assetripper'),'--version'])]:
    ok,out=run(cmd);check(name,ok,out)
check('SteamCMD',(root/'.local/tools/steamcmd/steamcmd.sh').exists(),'Run .local/tools/steamcmd/steamcmd.sh +quit to reverify')
ok,_=run(['gh','auth','status']);check('GitHub authentication',ok,'Authenticated' if ok else 'Run gh auth login')
ok,out=run([os.environ['ADB'],'devices']); devices=[l.split()[0] for l in out.splitlines()[1:] if len(l.split())>=2 and l.split()[1]=='device']
check('ADB target',len(devices)==1,'Exactly one authorized device required; found '+str(len(devices)))
if len(devices)==1:
    base=[os.environ['ADB'],'-s',devices[0],'shell']
    ok,abi=run(base+['getprop ro.product.cpu.abilist']);check('Target ARM64',ok and 'arm64-v8a' in abi,abi)
    ok,vols=run(base+['sm list-volumes all']); private=[l.split() for l in vols.splitlines() if l.startswith('private:') and ' mounted ' in l]
    check('Adopted storage mounted',ok and private,vols)
    for v in private:
        ok,out=run(base+['df -k /mnt/expand/'+v[2]])
        try: free=int(out.splitlines()[-1].split()[3]);check('Adopted free space',ok and free>1024*1024,f'{free/1024/1024:.1f} GiB free (minimum check: 1 GiB)')
        except (ValueError,IndexError):check('Adopted free space',False,out)
    ok,out=run(base+['df -k /data']);check('Internal storage query',ok,out)
ok,out=run(['codex','mcp','get','unity-bootstrap']);check('Unity MCP configuration',ok and '127.0.0.1:8080/mcp' in out,'unity-bootstrap at loopback port 8080')
python=root/'.local/tools/unity-mcp/Server/.venv/bin/python'
ok,out=run([str(python),str(root/'scripts/mcp-check.py')],40)
check('Unity MCP server responds',ok,'MCP initialize/tools/resources probe' if ok else out[-500:])
if ok:
    d=json.loads(out); inst=d.get('mcpforunity://instances',{})
    texts=' '.join(x.get('text','') for x in inst.get('contents',[]))
    try:
        obj=json.loads(texts); instances=obj.get('instances',obj.get('data',{}).get('instances',[])); connected=bool(instances)
    except (ValueError,AttributeError):connected=False
    check('Unity editor MCP connected',connected,texts[:800])
smoke=root/'environment/smoke-result.json'
passed=smoke.exists() and json.loads(smoke.read_text()).get('success',False)
check('Completed ARM64 device smoke test',passed,str(smoke))
result={'checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'ready':all(c['ok'] for c in checks),'checks':checks}
if '--json' in sys.argv:print(json.dumps(result,indent=2))
else:
    for c in checks:print(('OK   ' if c['ok'] else 'FAIL ')+c['name']+': '+str(c['detail']).replace('\n',' | '))
    print('READY' if result['ready'] else 'PARTIALLY READY')
sys.exit(0 if result['ready'] else 1)
