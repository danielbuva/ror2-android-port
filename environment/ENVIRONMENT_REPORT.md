# Environment bootstrap report

**READY — verified 2026-09-12 PDT.** Unity ARM64 Android build, real-device launch/log/screenshot, adopted-volume installation, and Unity MCP editor exercise passed. No Risk of Rain 2 porting or wholesale decompilation was performed.

## 1. Host summary

macOS **26.6.2**, build **25G83**, Apple Silicon **arm64**, zsh, 16 GiB RAM. Discovery found about 363 GiB free on the host data volume; sufficient for this bootstrap. Live disk/version data is in `tool-versions.json`. Xcode Command Line Tools: `/Library/Developer/CommandLineTools`. Native Homebrew: `/opt/homebrew`.

Initial PATH had duplicate entries, an unexpanded literal `~/.dotnet/tools`, and app-bundled rg/codex. .NET was not discoverable. `source scripts/env.sh` selects deterministic tools without changing global shell configuration. The global OpenJDK 26 must not be used for this Unity Android build.

## 2. Installed tools

Exact paths, version output, and Homebrew package inventory: **`environment/tool-versions.json`**. The baseline includes Git 2.55.0, gh 2.96.0, jq 1.7.1 (Apple), ripgrep 15.2.0, fd 10.5.0, Python 3.14.7, uv 0.12.13, .NET SDK 10.0.401, CMake 4.4.0, Ninja 1.13.2, pkg-config 3.0.4, sevenzip 26.02, ImageMagick 7.1.2-31, ffmpeg 9.0.1, scrcpy 4.1, curl, wget, Node 26.5.0 and npm 11.17.0. Existing tools were retained where usable; Homebrew resolved dependencies for the missing tools.

- **AssetRipper 2.0.0**: official macOS ARM64 executable, `.local/tools/assetripper/AssetRipper.GUI.Free`. Help and version commands passed. Use `./scripts/assetripper --headless`. No game was imported.
- **ilspycmd 11.0.0.9375**: installed under `$HOME/.local/bin`, wrapper `./scripts/ilspycmd`. Native .NET root `$HOME/.local/share/dotnet`. Version execution passed.
- **SteamCMD 1788292693**: `.local/tools/steamcmd/steamcmd.sh`; official Valve archive, updated universal ARM64/x86_64 executable. Native ARM64 startup and quit passed.
- Optional Ghidra deferred: native game inspection is outside bootstrap scope; ILSpy and AssetRipper cover the immediately useful inspection baseline.

## 3. Exact Unity editor and Android modules

The installed game's `Risk of Rain 2_Data/globalgamemanagers` header contains **2021.3.33f1** at byte offset 48. Only the header was inspected. Official archive confirms revision **ee5a2aa03ab2**.

Unity Hub **3.21.2** installed the exact **native ARM64** editor and every requested Android module successfully. Editor logs confirm it runs without Rosetta. Paths:

| Component | Verified path/version |
| --- | --- |
| Editor | `/Applications/Unity/Hub/Editor/2021.3.33f1/Unity.app/Contents/MacOS/Unity` |
| Android module root | `/Applications/Unity/Hub/Editor/2021.3.33f1/PlaybackEngines/AndroidPlayer` |
| SDK | `<Android module root>/SDK`; tools 26.1.1, build-tools 30.0.2, platform-tools 30.0.4, platforms API 29 rev 5 and API 30 rev 3 |
| NDK | `<Android module root>/NDK`; r21d, **21.3.6528147** |
| JDK | `<Android module root>/OpenJDK`; bundled **8u172** distribution; runtime reports `1.8.0-adoptopenjdk` |
| Gradle | `<Android module root>/Tools/gradle`; **6.1.1** |

AndroidPlayer is **beside Unity.app**, not inside `Unity.app/Contents`; the editor's registered module path and successful build verify this layout. Bundled Android tools include legacy Intel executables; existing Rosetta support works. Do not replace the matching SDK/NDK/JDK with Homebrew's newer tools implicitly.

The existing global Android debug keystore could not be read by the bundled JDK. The build script now isolates **ANDROID_SDK_HOME**, **ANDROID_USER_HOME**, and **GRADLE_USER_HOME** under ignored `.local/` paths. Gradle creates a disposable compatible debug keystore there; the user's existing key is untouched. These are test signatures, not release signing credentials.

## 4. Canonical ADB

Use **`/opt/homebrew/bin/adb`**, version **37.0.1 / 1.0.41**. Unity also bundles ADB 30.0.4 under its SDK; use that SDK for builds and the canonical Homebrew ADB for device automation. Unity can restart the ADB server when its version differs; re-query connectivity after editor activity. No additional ADB MCP is needed.

## 5. Android device profile

**`environment/device-profile.json`** contains the live captured values: serial `AUTHORIZED_SERIAL`, **Retroid Pocket Nova / QCS8550 / Adreno 740**, Android **13 / API 33**, ABI `arm64-v8a` plus advertised 32-bit ABIs. About 11 GiB RAM, about 6.4 GiB available at initial capture. Display **960×1280**, **60/120 Hz** modes. Build fingerprint is recorded in the JSON.

Advertised Vulkan feature version **4206592 = 1.3.0**, level 1, compute supported. This feature declaration is separate from an application's driver selection. SurfaceFlinger reports Qualcomm GLES V@0676.53. The smoke log records the GPU actually used by Unity.

Requested **MrPurple T30 toasted** driver release is recorded in `turnip-target.json`, published 2026-08-17. Official archive is staged under `.local/downloads/`, SHA-256 **f65b2d3353fd4aa7190bb5426b94468e99ffea7a58a830bc0c4651db89353227**, matching the release digest. No custom driver was installed or selected. A future native application's custom-driver integration is not validated by this smoke test.

## 6. Adopted storage findings

**Physical internal `/data` is nearly full: about 2.7 GiB free of 100.8 GiB.** Future work must not assume space for large APKs or payloads.

Mounted private/adopted f2fs volume **`private:179,2`**, UUID **`REDACTED_UUID`**, has approximately **425 GiB free of 922 GiB**. Its system mount is `/mnt/expand/<UUID>`; emulated shared storage is also backed by the adopted volume. `df` can display a bind-mount destination, so the profile records explicit path queries. Existing packages have code paths under `/mnt/expand/<UUID>/app/.../base.apk`.

Global install location remains **`0[auto]`**. The test manifest declares **`android:installLocation="auto"`**. Android selected `/data/app` for the first small-APK test. A second installation used the device-supported **per-install `--force-uuid <adopted UUID>` option**, and the package was installed and launched successfully from the adopted volume. This option did not change global settings or move any existing packages. Both test installations were uninstalled successfully.

Recommended default for suitable future manifests: `auto`, or `preferExternal` when app behavior warrants it. Neither guarantees placement. For local testing on this device, the verified per-install UUID option is available. Query the live UUID; never assume a portable SD path. Use Android application storage APIs for runtime data. Large payloads, installation scratch-space requirements, and behavior with even less physical free space remain untested.

## 7. MCP and GitHub integrations

Public repository: **https://github.com/danielbuva/ror2-android-port**. Authentication state and session details are local-only.

**CoplayDev Unity MCP v10.2.0** is pinned in `smoke/Packages/manifest.json` and the local server clone. It declares minimum Unity 2021.3 and successfully compiled in the exact editor. Dependencies were installed from the server lockfile.

Codex global MCP entry **`unity-bootstrap`** points to **`http://127.0.0.1:8080/mcp`**. Loopback only; no cloud authentication. Start server: `./scripts/mcp-server.sh`. Open the isolated editor and connect: `./scripts/open-smoke.sh`, or Window > MCP for Unity in an already-open editor. The server/editor are left running at handoff.

Verification:

```sh
.local/tools/unity-mcp/Server/.venv/bin/python scripts/mcp-check.py
.local/tools/unity-mcp/Server/.venv/bin/python scripts/mcp-exercise.py
```

The read-only probe checks MCP initialize/tools/resources and editor instances. The exercise guards the project path, loads the smoke scene, reads hierarchy, enters Play Mode, reads the distinctive marker from the Unity console, exits Play Mode, and activates the testing tool group. **All passed**, evidence in `mcp-exercise.json`. Scene/assets/components, console, Play Mode, test tools and build tools are exposed. Test execution and MCP-triggered builds were not separately exercised; the actual Android build is verified through the deterministic Unity CLI script. Enable the `testing` group with `manage_tools` when `run_tests`/`get_test_job` are not visible.

## 8. Authentication and legitimate game acquisition

Authentication and activation are local prerequisites. Session history and license/account state are intentionally excluded from the public report.

Configure the external legitimate Windows game installation in ignored `work/config/local.json`; no user-specific installation path is published.

SteamCMD startup/update/quit was verified without login. A future fresh Windows download can select `@sSteamCmdForcePlatformType windows`, choose a new destination, authenticate interactively, and request `app_update 632360 validate`. Steam login/Guard is required only for that future account-dependent download; do not put credentials in command history or files. Existing CrossOver Steam is also available. No files were copied into Git or changed in the game installation.

## 9. Smoke-test result

**PASS.** Source-only project `smoke/`, Unity **2021.3.33f1**, **IL2CPP ARM64**, **Development**, minimum API 23, target API 30 using the bundled SDK. Target API 30 is for this local device test, not a claim of current store-submission compliance.

- APK: `builds/bootstrap-arm64.apk`, about **12 MiB**; `aapt` verifies native code **only arm64-v8a**.
- Package: `dev.localbootstrap.arm64smoke`.
- Default install, launch, filtered PID logcat, marker, screenshot, stop and uninstall passed.
- Adopted-volume install, launch, log marker, screenshot, path/volume verification, stop and uninstall also passed.
- Marker: **`ROR2_BOOTSTRAP_ARM64_OK`**.
- Evidence: `smoke-auto-result.json`, `smoke-result.json`, `smoke-logcat.txt`, `smoke-screenshot.png`.
- Screenshot visually checked: obvious ARM64 bootstrap text on the test background and Development Build indicator.
- scrcpy **4.1** connected and recorded a three-second stream. Interactive input control was not separately exercised.

Reproduce (close the smoke editor before the batch build):

```sh
./scripts/build-smoke.sh
python3 scripts/smoke-device.py --adopted
```

Omit `--adopted` to measure Android's default placement. The script refuses a pre-existing smoke package and removes only the package it installs. Keys, APKs, raw editor logs and caches are ignored by Git. Unity failure logs can include environment variables; do not publish raw logs.

## 10. Single health check

**`./scripts/doctor.sh`**; JSON: **`./scripts/doctor.sh --json`**. The final live run passes all checks and returns zero; captured output is `doctor-result.json`.

It verifies required tools, exact editor/module paths, ADB authorization, ARM64 ABI, mounted adopted storage/free space, MCP configuration/protocol/editor connectivity, acquisition/inspection tools, and recorded acceptance evidence. It does not depend on proprietary game files and does not rebuild/reinstall by itself. With the device disconnected or the editor/server closed it correctly fails; reconnect or use the startup commands above.

## 11. Limits and Agent #2 handoff

No bootstrap blocker remains. **Agent #2: read this report and run `./scripts/doctor.sh` before planning the port.** Bootstrap completion is not evidence that RoR2 itself runs, that large game payload placement is solved, or that the custom Turnip driver is integrated. Those belong to later authorized work.

## Sources

- https://unity.com/releases/editor/whats-new/2021.3.33f1
- https://docs.unity.com/en-us/hub/use-hub-cli
- https://learn.chatgpt.com/docs/extend/mcp?surface=cli
- https://github.com/CoplayDev/unity-mcp/tree/v10.2.0
- https://github.com/AssetRipper/AssetRipper/releases/tag/2.0.0
- https://github.com/MrPurple666/purple-turnip/releases/tag/vturnip_mrpurple_T30-toasted.adpkg
- https://developer.valvesoftware.com/wiki/SteamCMD
- https://developer.android.com/tools/variables
