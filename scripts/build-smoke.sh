#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/env.sh
mkdir -p builds .local/logs
"$UNITY_EDITOR" -batchmode -quit -projectPath "$PWD/smoke" -buildTarget Android -executeMethod BootstrapBuild.Build -logFile "$PWD/.local/logs/unity-build.log"
test -f builds/bootstrap-arm64.apk
