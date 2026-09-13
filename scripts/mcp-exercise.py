#!/usr/bin/env python3
"""Exercise only the isolated bootstrap editor. Never target another project."""
import asyncio,json
from pathlib import Path
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
root=Path(__file__).resolve().parents[1]
def payload(result):
    for item in result.content:
        if getattr(item,'type',None)=='text':
            try:return json.loads(item.text)
            except ValueError:pass
    return result.model_dump(mode='json')
async def main():
    evidence={}
    async with streamablehttp_client('http://127.0.0.1:8080/mcp') as (read,write,_):
        async with ClientSession(read,write) as s:
            await s.initialize()
            info=await s.read_resource('mcpforunity://instances')
            instances=json.loads(info.contents[0].text)['instances']
            evidence['instances']=instances
            project=await s.read_resource('mcpforunity://project/info')
            evidence['project']=project.model_dump(mode='json')
            if len(instances)!=1 or str(root/'smoke') not in json.dumps(evidence['project']):
                raise RuntimeError('Expected exactly the bootstrap smoke editor instance')
            async def call(name,args):
                result=await s.call_tool(name,args);data=payload(result)
                if result.isError or data.get('success') is False:raise RuntimeError(f'{name}: {data}')
                return data
            evidence['load']=await call('manage_scene',{'action':'load','path':'Assets/Bootstrap.unity'})
            evidence['scene']=await call('manage_scene',{'action':'get_hierarchy'})
            evidence['play']=await call('manage_editor',{'action':'play'})
            try:
                await asyncio.sleep(3)
                evidence['console']=await call('read_console',{'action':'get','filter_text':'ROR2_BOOTSTRAP_ARM64_OK','count':'10'})
            finally:evidence['stop']=await call('manage_editor',{'action':'stop'})
            evidence['testing_group']=await call('manage_tools',{'action':'activate','group':'testing'})
            evidence['tools_after_testing_enabled']=[t.name for t in (await s.list_tools()).tools]
            evidence['success']='ROR2_BOOTSTRAP_ARM64_OK' in json.dumps(evidence['console'])
    (root/'environment/mcp-exercise.json').write_text(json.dumps(evidence,indent=2)+'\n')
    print(json.dumps(evidence,indent=2))
    if not evidence['success']:raise RuntimeError('Editor marker missing')
asyncio.run(asyncio.wait_for(main(),90))
