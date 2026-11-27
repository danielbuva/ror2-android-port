#!/bin/sh
# Source this file for deterministic bootstrap tool selection.
export DOTNET_ROOT="$HOME/.local/share/dotnet"
export PATH="/opt/homebrew/bin:$DOTNET_ROOT:$HOME/.local/bin:$PATH"
export UNITY_EDITOR="/Applications/Unity/Hub/Editor/2021.3.45f2/Unity.app/Contents/MacOS/Unity"
export UNITY_ANDROID_ROOT="/Applications/Unity/Hub/Editor/2021.3.45f2/PlaybackEngines/AndroidPlayer"
export ANDROID_HOME="$UNITY_ANDROID_ROOT/SDK"
export ANDROID_SDK_ROOT="$ANDROID_HOME"
export ANDROID_NDK_ROOT="$UNITY_ANDROID_ROOT/NDK"
export JAVA_HOME="$UNITY_ANDROID_ROOT/OpenJDK"
export ADB="/opt/homebrew/bin/adb"
# Unity's Android module kills every running adb server that was not started
# from its own SDK (EditorPrefs AndroidADBKillExternalInstance, default on).
# The lab shares one Homebrew adb server, so a single editor launch would drop
# every device mid-transfer. Keep that preference off for all editors.
if [ "$(uname -s)" = Darwin ] && command -v defaults >/dev/null 2>&1; then
    [ "$(defaults read com.unity3d.UnityEditor5.x AndroidADBKillExternalInstance 2>/dev/null)" = 0 ] ||
        defaults write com.unity3d.UnityEditor5.x AndroidADBKillExternalInstance -int 0 2>/dev/null || true
fi
