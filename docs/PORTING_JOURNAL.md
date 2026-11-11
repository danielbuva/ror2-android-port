# Porting journal

## J1400 -- Retarget Android port to x86_64 and configure single APK GitHub Actions workflow

2026-11-11. Retargeted `environment/toolchain.json`, Unity Editor `LabBuild.cs`, `smoke/ProjectSettings/ProjectSettings.asset`,
`recipe/owner-native-x86_64.json`, `native.py`, `produce.py`, `build_owner_apk.py`, and `sdk_package.py` from `arm64-v8a`
to `x86_64` (x64). Replaced multi-workflow host checks with a single `.github/workflows/build-apk.yml` pipeline that
compiles the native `x86_64` C++/JNI libraries (`libil2cpp.so`, `libror2_x64_bridge.so`) and packages the signed x64 APK.
