#!/bin/sh
cd "$(dirname "$0")/.."
export UNITY_MCP_TELEMETRY_ENABLED=false
exec /opt/homebrew/bin/uv run --frozen --project .local/tools/unity-mcp/Server mcp-for-unity --transport http --http-host 127.0.0.1 --http-port 8080
