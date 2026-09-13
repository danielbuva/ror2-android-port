"""Pinned Unity MCP client; project selection is checked before every action."""
import asyncio,json,sys,datetime
from pathlib import Path
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
ROOT=Path(__file__).resolve().parents[2]
async def main():
 target,action=sys.argv[1:3]; expected=(ROOT/'work/lab-project') if target=='lab' else (ROOT/'smoke') if target=='smoke' else Path(json.loads((ROOT/'work/config/reconstruction.json').read_text())['projects'][0]);expected=expected if expected.is_absolute() else ROOT/expected
 out=ROOT/'work/editor';out.mkdir(parents=True,exist_ok=True);archive=out/(datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')+'-'+target+'-'+action);archive.mkdir();evidence={'target':str(expected),'action':action}
 async with streamablehttp_client('http://127.0.0.1:8080/mcp') as (r,w,_):
  async with ClientSession(r,w) as s:
   await s.initialize()
   async def call(name,args):
    row={'tool':name,'args':args,'status':'sent'};evidence.setdefault('calls',[]).append(row)
    (out/(target+'-'+action+'-progress.json')).write_text(json.dumps(evidence,indent=2)+'\n')
    (archive/'progress.json').write_text(json.dumps(evidence,indent=2)+'\n')
    response=await s.call_tool(name,args)
    row['status']='returned';row['response']=response.model_dump(mode='json')
    (out/(target+'-'+action+'-progress.json')).write_text(json.dumps(evidence,indent=2)+'\n')
    texts=[x.text for x in response.content if getattr(x,'type',None)=='text'];data=json.loads(texts[0]) if texts else {}
    (archive/'progress.json').write_text(json.dumps(evidence,indent=2)+'\n')
    if response.isError or data.get('success') is False:raise RuntimeError(str(data))
    return data
   instances=json.loads((await s.read_resource('mcpforunity://instances')).contents[0].text)['instances'];matches=[i for i in instances if i['name']==expected.name]
   if len(matches)!=1:raise RuntimeError('Expected one connected editor named '+expected.name+'; found '+str(instances))
   evidence['selection']=await call('set_active_instance',{'instance':matches[0]['id']})
   project=(await s.read_resource('mcpforunity://project/info')).model_dump(mode='json');evidence['project']=project
   if str(expected) not in json.dumps(project):raise RuntimeError('MCP selected project path mismatch')
   if action=='build':evidence['result']=await call('execute_menu_item',{'menu_path':'Porting Lab/Build ARM64'})
   elif action=='backend':evidence['result']=await call('execute_menu_item',{'menu_path':'Porting Lab/Record Backend Constraints'})
   elif action=='refresh':evidence['result']=await call('refresh_unity',{'mode':'force','scope':'all','compile':'request','wait_for_ready':True})
   elif action=='load':
    scenes=list(expected.glob('Assets/**/loadingbasic.unity'))
    if len(scenes)!=1:raise RuntimeError('Expected one recovered loadingbasic scene')
    evidence['load']=await call('manage_scene',{'action':'load','path':str(scenes[0].relative_to(expected))})
    evidence['hierarchy']=await call('manage_scene',{'action':'get_hierarchy'})
   elif action=='loadplay':
    scenes=list(expected.glob('Assets/**/loadingbasic.unity'))
    if len(scenes)!=1:raise RuntimeError('Expected one recovered loadingbasic scene; found '+str(scenes))
    evidence['load']=await call('manage_scene',{'action':'load','path':str(scenes[0].relative_to(expected))})
    evidence['hierarchy']=await call('manage_scene',{'action':'get_hierarchy'})
    evidence['play']=await call('manage_editor',{'action':'play'});await asyncio.sleep(8)
    try:evidence['console']=await call('read_console',{'action':'get','count':'100','include_stacktrace':True})
    finally:evidence['stop']=await call('manage_editor',{'action':'stop'})
   elif action=='probe':evidence['result']=await call('execute_menu_item',{'menu_path':'Porting Lab/Inspect Reconstruction'})
   elif action=='minimal-build':evidence['result']=await call('execute_menu_item',{'menu_path':'Porting Lab/Build Reconstruction Minimum'})
   elif action=='play':
    evidence['play']=await call('manage_editor',{'action':'play'});await asyncio.sleep(5)
    evidence['console']=await call('read_console',{'action':'get','count':'100','include_stacktrace':True});evidence['stop']=await call('manage_editor',{'action':'stop'})
   else:
    evidence['hierarchy']=await call('manage_scene',{'action':'get_hierarchy'})
    evidence['console']=await call('read_console',{'action':'get','count':'100','include_stacktrace':True})
   evidence['success']=True
 (archive/'result.json').write_text(json.dumps(evidence,indent=2)+'\n')
 (out/(target+'-'+action+'.json')).write_text(json.dumps(evidence,indent=2)+'\n');print(json.dumps(evidence,indent=2))
asyncio.run(asyncio.wait_for(main(),180))
