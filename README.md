# Risk of Rain 2 — Android x64 (`x86_64`) Port (`san5ezez/ror2-android-port`)

Unofficial Android **x64 (`x86_64`)** port, launcher, and conversion toolchain for **Risk of Rain 2**, adapted from `danielbuva/ror2-android-port` and configured to build a ready-to-install **x64 APK** directly on GitHub Actions.

## Key Changes in This Repository

1. **Retargeted to x64 (`x86_64`) across the entire stack**:
   - `environment/toolchain.json`: `"architecture": "x86_64"`
   - `android/Assets/Editor/LabBuild.cs`, `Il2CppInvocationCapture.cs`, `PlayerLinkerInputCapture.cs`: `AndroidArchitecture.X86_64`, `jniLibs/x86_64/libil2cpp.so`, package ID `dev.ror2lab.x86_64`.
   - `smoke/ProjectSettings/ProjectSettings.asset` & `smoke/Assets/Editor/BootstrapBuild.cs`: `AndroidTargetArchitectures: 8` (`X86_64`).
   - `recipe/owner-native-x86_64.json` & `recipe/owner-native-arm64.json`: retargeted to `-march=x86-64`, `-target x86_64-linux-android22`, `x86_64-linux-android/bin/objcopy`, and `StaticLibs/x86_64/baselib.a`.
   - `tools/phone-build/owner-code/native.py`, `produce.py`, `tools/phone-build/owner-apk/build_owner_apk.py`, `tools/phone-build/accepted-output/sdk_package.py`: updated for `lib/x86_64/` and ELF `EM_X86_64` (`e_machine = 62`).
2. **Single GitHub Actions Workflow (`.github/workflows/build-apk.yml`)**:
   - All legacy host/lab/release workflows have been replaced with a single **`build-apk`** workflow that compiles the native x64 (`x86_64`) JNI library via Android NDK Clang, packages the Android Launcher & Payload Bootstrap APK (`ror2-android-x64-debug.apk`), signs it with `apksigner`, and uploads the `.apk` artifact on every push, pull request, or manual dispatch.

## Building the APK Locally or on GitHub

- **On GitHub**: Push this repository to [`https://github.com/san5ezez/ror2-android-port`](https://github.com/san5ezez/ror2-android-port). The **Build x64 APK** workflow runs automatically and publishes `ror2-android-x64-apk` (`ror2-android-x64-debug.apk`) in the **Actions** tab (and attaches it to Releases when pushing a `v*` tag).
- **Locally with Gradle + Android SDK/NDK**:
  ```bash
  ./gradlew assembleDebug
  ```
  The signed x64 APK will be written to `app/build/outputs/apk/debug/ror2-android-x64-debug.apk`.
