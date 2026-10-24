"""Pinned Unity MCP client; project selection is checked before every action."""

import asyncio
import json
import os
import sys
import datetime
from pathlib import Path
from common import WORK, lane_config
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/lab"))
from build_lock import (
    HOST_BUILD_LOCK,
    INHERITED_FD_ENV,
    assert_build_unblocked,
    assert_host_build_lock_held,
    host_build_lock,
)


async def _main():
    target, action = sys.argv[1:3]
    expected = (
        (WORK / "lab-project")
        if target == "lab"
        else (ROOT / "smoke")
        if target == "smoke"
        else Path(json.loads((ROOT / "work/config/reconstruction.json").read_text())["projects"][0])
    )
    expected = (expected if expected.is_absolute() else ROOT / expected).resolve()
    out = WORK / "editor"
    out.mkdir(parents=True, exist_ok=True)
    archive = out / (datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ") + "-" + target + "-" + action)
    archive.mkdir()
    evidence = {"target": str(expected), "action": action}
    async with streamablehttp_client("http://127.0.0.1:" + str(lane_config().get("mcp_port", 8080)) + "/mcp") as (r, w, _):
        async with ClientSession(r, w) as s:
            assert_build_unblocked()
            assert_host_build_lock_held(HOST_BUILD_LOCK)
            await s.initialize()

            async def call(name, args):
                assert_build_unblocked()
                assert_host_build_lock_held(HOST_BUILD_LOCK)
                row = {"tool": name, "args": args, "status": "sent"}
                evidence.setdefault("calls", []).append(row)
                (out / (target + "-" + action + "-progress.json")).write_text(json.dumps(evidence, indent=2) + "\n")
                (archive / "progress.json").write_text(json.dumps(evidence, indent=2) + "\n")
                response = await s.call_tool(name, args)
                row["status"] = "returned"
                row["response"] = response.model_dump(mode="json")
                (out / (target + "-" + action + "-progress.json")).write_text(json.dumps(evidence, indent=2) + "\n")
                texts = [x.text for x in response.content if getattr(x, "type", None) == "text"]
                data = json.loads(texts[0]) if texts else {}
                (archive / "progress.json").write_text(json.dumps(evidence, indent=2) + "\n")
                if response.isError or data.get("success") is False:
                    raise RuntimeError(str(data))
                return data

            assert_build_unblocked()
            assert_host_build_lock_held(HOST_BUILD_LOCK)
            instances = json.loads((await s.read_resource("mcpforunity://instances")).contents[0].text)["instances"]
            matches = [i for i in instances if i["name"] == expected.name]
            if len(matches) != 1:
                raise RuntimeError("Expected one connected editor named " + expected.name + "; found " + str(instances))
            evidence["selection"] = await call("set_active_instance", {"instance": matches[0]["id"]})
            assert_build_unblocked()
            assert_host_build_lock_held(HOST_BUILD_LOCK)
            project = (await s.read_resource("mcpforunity://project/info")).model_dump(mode="json")
            evidence["project"] = project
            if str(expected) not in json.dumps(project):
                raise RuntimeError("MCP selected project path mismatch")
            version = json.loads((ROOT / "environment/toolchain.json").read_text())["unity_version"]
            evidence["editor_pin"] = await call(
                "execute_code",
                {
                    "action": "execute",
                    "code": 'if(BuildPipeline.isBuildingPlayer)throw new System.Exception("Outstanding Unity build must finish before another editor action");if(Application.unityVersion!='
                    + json.dumps(version)
                    + ')throw new System.Exception("Connected editor differs from approved exact pin");return Application.unityVersion;',
                },
            )
            if action == "build":
                evidence["compilation"] = await call(
                    "execute_code",
                    {
                        "action": "execute",
                        "code": 'if(EditorApplication.isCompiling||EditorApplication.isUpdating||EditorUtility.scriptCompilationFailed||BuildPipeline.isBuildingPlayer)throw new System.Exception("Current editor source is not compiled and idle; refuse stale build dispatch");return "currentEditorCompilation=true";',
                    },
                )
                evidence["result"] = await call("execute_menu_item", {"menu_path": "Porting Lab/Build ARM64"})
            elif action == "presentation-payload":
                evidence["result"] = await call("execute_menu_item", {"menu_path": "Porting Lab/Build Android Presentation Payload"})
            elif action == "character-motor-order":
                evidence["result"] = await call("execute_menu_item", {"menu_path": "Porting Lab/Restore Character Motor Order"})
            elif action == "catalog-addresses":
                evidence["result"] = await call("execute_menu_item", {"menu_path": "Porting Lab/Inspect Catalog Addresses"})
            elif action == "reference-identities":
                evidence["result"] = await call("execute_menu_item", {"menu_path": "Porting Lab/Inspect Reference Identities"})
            elif action == "siren-input-host":
                evidence["result"] = await call(
                    "execute_code",
                    {
                        "action": "execute",
                        "code": 'if(EditorApplication.isUpdating||EditorUtility.scriptCompilationFailed)throw new System.Exception("Current editor source is not compiled and idle");return SirenEggDiagnosticInputExactEditorFixture.Run();',
                    },
                )
            elif action == "source-camera-graphics-host":
                evidence["result"] = await call("execute_code", {"action": "execute", "code": "return SourceCameraGraphicsHost.Run();"})
            elif action == "backend":
                evidence["result"] = await call("execute_menu_item", {"menu_path": "Porting Lab/Record Backend Constraints"})
            elif action == "refresh":
                evidence["result"] = await call("refresh_unity", {"mode": "force", "scope": "all", "compile": "request", "wait_for_ready": True})
            elif action == "load":
                scenes = list(expected.glob("Assets/**/loadingbasic.unity"))
                if len(scenes) != 1:
                    raise RuntimeError("Expected one recovered loadingbasic scene")
                evidence["load"] = await call("manage_scene", {"action": "load", "path": str(scenes[0].relative_to(expected))})
                evidence["hierarchy"] = await call("manage_scene", {"action": "get_hierarchy"})
            elif action == "loadplay":
                scenes = list(expected.glob("Assets/**/loadingbasic.unity"))
                if len(scenes) != 1:
                    raise RuntimeError("Expected one recovered loadingbasic scene; found " + str(scenes))
                evidence["load"] = await call("manage_scene", {"action": "load", "path": str(scenes[0].relative_to(expected))})
                evidence["hierarchy"] = await call("manage_scene", {"action": "get_hierarchy"})
                evidence["play"] = await call("manage_editor", {"action": "play"})
                await asyncio.sleep(8)
                try:
                    evidence["console"] = await call("read_console", {"action": "get", "count": "100", "include_stacktrace": True})
                finally:
                    evidence["stop"] = await call("manage_editor", {"action": "stop"})
            elif action == "probe":
                evidence["result"] = await call("execute_menu_item", {"menu_path": "Porting Lab/Inspect Reconstruction"})
            elif action == "minimal-build":
                evidence["result"] = await call("execute_menu_item", {"menu_path": "Porting Lab/Build Reconstruction Minimum"})
            elif action == "play":
                evidence["play"] = await call("manage_editor", {"action": "play"})
                await asyncio.sleep(5)
                evidence["console"] = await call("read_console", {"action": "get", "count": "100", "include_stacktrace": True})
                evidence["stop"] = await call("manage_editor", {"action": "stop"})
            else:
                evidence["hierarchy"] = await call("manage_scene", {"action": "get_hierarchy"})
                evidence["console"] = await call("read_console", {"action": "get", "count": "100", "include_stacktrace": True})
            evidence["success"] = True
    (archive / "result.json").write_text(json.dumps(evidence, indent=2) + "\n")
    (out / (target + "-" + action + ".json")).write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(evidence, indent=2))


async def main():
    target, action = sys.argv[1:3]
    assert_build_unblocked()
    if action == "minimal-build":
        raise RuntimeError("The historical minimal-build editor action is unsupported; use ./dev build")
    if action in {"build", "presentation-payload"} and (os.environ.get("ROR2LAB_COORDINATED_BUILD") != "1" or INHERITED_FD_ENV not in os.environ):
        raise RuntimeError("Direct editor build dispatch is disabled; use the build coordinator")
    with host_build_lock(HOST_BUILD_LOCK, operation=f"editor:{target}:{action}"):
        assert_build_unblocked()
        await _main()


asyncio.run(asyncio.wait_for(main(), 180))
