#!/usr/bin/env python3
import asyncio, json, sys
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
async def main():
    async with streamablehttp_client('http://127.0.0.1:8080/mcp') as (read,write,_):
        async with ClientSession(read,write) as session:
            init=await session.initialize()
            tools=await session.list_tools()
            resources=await session.list_resources()
            result={'server':init.serverInfo.model_dump(),'tools':[t.name for t in tools.tools],'resources':[str(r.uri) for r in resources.resources]}
            for uri in result['resources']:
                if 'instances' in uri or 'editor_state' in uri:
                    result[uri]=(await session.read_resource(uri)).model_dump(mode='json')
            print(json.dumps(result,indent=2))
asyncio.run(asyncio.wait_for(main(),30))
