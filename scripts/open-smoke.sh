#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/env.sh
mkdir -p .local/logs
if ! curl -fsS --max-time 2 http://127.0.0.1:8080/health >/dev/null; then
    nohup ./scripts/mcp-server.sh > .local/logs/mcp-server.log 2>&1 &
    for attempt in {1..20}; do
        if curl -fsS --max-time 2 http://127.0.0.1:8080/health >/dev/null 2>&1; then break; fi
        sleep 1
    done
fi
if test -f smoke/Temp/UnityLockfile; then
    echo 'Smoke editor appears open. Use Window > MCP for Unity to connect, or close it before rerunning.'
    exit 1
fi
open -a "${UNITY_EDITOR%/Contents/MacOS/Unity}" --args -projectPath "$PWD/smoke" -executeMethod BootstrapMcp.Connect -logFile "$PWD/.local/logs/unity-editor.log"
echo 'Opening the isolated smoke editor and connecting Unity MCP.'
