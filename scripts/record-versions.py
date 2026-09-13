#!/usr/bin/env python3
import datetime,json,os,platform,shutil,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1]
def run(args):
 try:
  p=subprocess.run(args,capture_output=True,text=True,timeout=20)
  return {'ok':p.returncode==0,'output':(p.stdout+p.stderr).strip()[:3000]}
 except (OSError,subprocess.TimeoutExpired) as e:return {'ok':False,'output':str(e)}
commands={'git':['git','--version'],'gh':['gh','--version'],'jq':['jq','--version'],'rg':['rg','--version'],'fd':['fd','--version'],'curl':['curl','--version'],'wget':['wget','--version'],'python':['python3','--version'],'uv':['uv','--version'],'dotnet':['dotnet','--info'],'node':['node','--version'],'npm':['npm','--version'],'cmake':['cmake','--version'],'ninja':['ninja','--version'],'pkg-config':['pkg-config','--version'],'sevenzip':['7zz'],'imagemagick':['magick','--version'],'ffmpeg':['ffmpeg','-version'],'scrcpy':['scrcpy','--version'],'adb':['/opt/homebrew/bin/adb','version'],'ilspycmd':[str(root/'scripts/ilspycmd'),'--version'],'assetripper':[str(root/'scripts/assetripper'),'--version'],'system_java':['/opt/homebrew/bin/java','-version'],'unity_java':[os.environ['JAVA_HOME']+'/bin/java','-version']}
data={'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'host':{'architecture':platform.machine(),'macos':run(['sw_vers']),'disk':run(['df','-k',str(root)]),'clt':run(['xcode-select','-p'])},'tools':{k:{'path':shutil.which(v[0]),**run(v)} for k,v in commands.items()},'homebrew':run(['brew','list','--versions']),'unity_version':'2021.3.33f1','unity_revision':'ee5a2aa03ab2','unity_mcp':'10.2.0','steamcmd':'1788292693'}
(root/'environment/tool-versions.json').write_text(json.dumps(data,indent=2)+'\n')
