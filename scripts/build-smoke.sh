#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/env.sh
mkdir -p builds .local/logs .local/android-user/.android
# Isolate legacy Gradle debug signing from the user's existing keystore.
export ANDROID_SDK_HOME="$PWD/.local/android-user"
export ANDROID_USER_HOME="$ANDROID_SDK_HOME/.android"
# Use a fresh daemon/cache so old Gradle cannot retain another build's Android location.
export GRADLE_USER_HOME="$PWD/.local/gradle"
"$UNITY_EDITOR" -batchmode -quit -projectPath "$PWD/smoke" -buildTarget Android -executeMethod BootstrapBuild.Build -logFile "$PWD/.local/logs/unity-build.log"
test -f builds/bootstrap-arm64.apk
