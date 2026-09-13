# Environment bootstrap report

Status: **PARTIALLY READY — installation and acceptance checks in progress**.

Scope: environment setup only; no game porting, wholesale decompilation, or architectural decisions. No proprietary assets are stored in this repository.

## Host

macOS 26.6.2, build 25G83, Apple Silicon arm64; zsh; 16 GiB RAM. Discovery found approximately 363 GiB free on the host data volume. Xcode Command Line Tools are installed at `/Library/Developer/CommandLineTools`. Native Homebrew is `/opt/homebrew`.

The initial PATH contained a literal `~/.dotnet/tools` entry (not shell-expanded), duplicates, and app-bundled rg/codex. The .NET SDK was not discoverable. Source `scripts/env.sh` to select deterministic tools without rewriting the user's global shell configuration. System Java is OpenJDK 26 and is unsuitable as the default for this Unity version's Android build; use the Unity-bundled JDK instead.

## Tools

See `tool-versions.json` for machine-readable versions. Installed fd, uv, standalone ripgrep, ImageMagick, scrcpy, Unity Hub, native .NET 10 SDK, ilspycmd, AssetRipper, SteamCMD, and Unity MCP dependencies. Existing Git, gh, jq, Python, CMake, Ninja, pkg-config, sevenzip, ffmpeg, curl, wget, Android platform tools, and Android command-line tools were retained. Optional Ghidra is deferred: no native game inspection is required for bootstrap.

AssetRipper: `.local/tools/assetripper/AssetRipper.GUI.Free`, official 2.0.0 macOS ARM64 release, executable verified. Launch with `./scripts/assetripper --headless`; no game files have been imported. ILSpy: `./scripts/ilspycmd`, version 11.0.0.9375; .NET root `$HOME/.local/share/dotnet`, SDK 10.0.401 ARM64.

## Exact Unity toolchain

The installed game's `Risk of Rain 2_Data/globalgamemanagers` header contains **2021.3.33f1** at byte offset 48. Only the header was inspected. Official archive confirms revision `ee5a2aa03ab2` and a macOS ARM64 editor.

Installation is in progress through Unity Hub 3.21.2, explicitly selecting arm64 and Android Build Support, SDK/NDK children, and OpenJDK. Expected paths (not yet validated):

- Editor: `/Applications/Unity/Hub/Editor/2021.3.33f1/Unity.app/Contents/MacOS/Unity`
- Android module root: `/Applications/Unity/Hub/Editor/2021.3.33f1/Unity.app/Contents/PlaybackEngines/AndroidPlayer`
- SDK, NDK, OpenJDK: corresponding children of the Android module root.

These bundled tools are authoritative for Unity builds; the existing Homebrew Android SDK and Java must not replace them implicitly. Device operations use canonical `/opt/homebrew/bin/adb`, version 37.0.1.

## Device and adopted storage

See `device-profile.json`, captured with read-only ADB commands. Device: Retroid Pocket Nova, QCS8550, Adreno 740, Android 13/API 33, ABI arm64-v8a (also advertises 32-bit ABIs). About 11 GiB total RAM, 6.4 GiB available at capture. Display 960×1280, 60/120 Hz modes. Vulkan feature version 4206592 decodes to 1.3.0; this is an Android advertised feature, not a measured application driver result.

Physical internal `/data`: approximately 2.75 GiB free out of 100.8 GiB. **Do not assume space for large APKs or game payloads.**

Adopted private volume `private:179,2` is mounted, UUID `REDACTED_UUID`, f2fs, approximately 425 GiB free out of 922 GiB. Its system mount is `/mnt/expand/<UUID>`. The emulated shared-storage backing also points to this adopted volume. Shell `df` may display a bind-mount destination instead of the requested path; use device-profile fields from explicit queries.

Existing installed packages have code paths under `/mnt/expand/<UUID>/app/.../base.apk`, proving this device supports adopted-volume app placement. Global package install setting is `0[auto]`, unchanged. Future manifests should generally declare `android:installLocation="auto"`, with `preferExternal` considered only for suitable app behavior. Android ultimately chooses placement; private app data and temporary installation requirements must be measured. Use Android application storage APIs, never hardcoded portable SD paths. The smoke test uses Auto and records actual placement. No storage configuration or existing game files were modified.

Requested driver reference: MrPurple T30 toasted `.adpkg`, release published 2026-08-17. Device SurfaceFlinger reports Qualcomm's GLES driver, not Turnip. No custom driver was installed or selected; compatibility and use in a future native application remain unverified.

## Integrations and repository

Public repository: **https://github.com/danielbuva/ror2-android-port**. Authentication state and session details are local-only.

CoplayDev Unity MCP **v10.2.0** is pinned in the smoke project's package manifest and local server clone. Package declares minimum Unity 2021.3. Python dependencies installed from its lockfile. Codex global MCP entry `unity-bootstrap` points to `http://127.0.0.1:8080/mcp`. Start with `./scripts/mcp-server.sh`; no public listening interface or cloud credentials are configured. MCP initialize, tools/list and resources/list succeed. Instance list currently contains no editor; end-to-end verification is pending Unity installation.

Probe: `.local/tools/unity-mcp/Server/.venv/bin/python scripts/mcp-check.py`. Open the smoke project, then Window > MCP for Unity, or launch Editor with `-executeMethod BootstrapMcp.Connect`. Capabilities include editor state, scenes/assets/components, Play Mode, console, tests and builds; advertised tools are recorded in `mcp-check.json`. No ADB MCP is needed.

## Legitimate Steam acquisition

Existing Windows installation: `/Users/LOCAL_USER/Library/Application Support/CrossOver/Bottles/New Bottle/drive_c/Program Files (x86)/Steam/steamapps/common/Risk of Rain 2`. Recorded in place; not copied into Git.

SteamCMD installed at `.local/tools/steamcmd/steamcmd.sh` from Valve's official macOS archive. Update/start/quit succeeds (version 1788292693). The updated executable is universal arm64/x86_64; the macOS archive initially stages an updater. For a later authenticated download, set `@sSteamCmdForcePlatformType windows`, choose a fresh download directory, then log in interactively and use `app_update 632360 validate`. Never validate over the user's existing installation without explicit intent. Existing Windows Steam in CrossOver is also a legitimate acquisition mechanism. No login/download is necessary to use the existing files.

## Smoke test and health check

Acceptance test is **pending**. Source-only throwaway project at `smoke/` contains a camera, visible bootstrap text, and `ROR2_BOOTSTRAP_ARM64_OK` marker. It selects IL2CPP ARM64, Development build, Android install location Auto, minimum API 23 and target API 30 (the matching editor's bundled platform; local device testing only).

Build: `./scripts/build-smoke.sh`. Device loop: `python3 scripts/smoke-device.py`. The loop refuses a pre-existing smoke package, installs only `dev.localbootstrap.arm64smoke`, launches it, captures PID-filtered Unity logs and a screenshot, records actual package placement, then stops/uninstalls it. Evidence goes to `environment/smoke-result.json`, `smoke-logcat.txt`, and `smoke-screenshot.png`.

scrcpy 4.1 successfully connected and recorded a three-second stream. Its control path has not yet been exercised.

Health check: **`./scripts/doctor.sh`**, or `./scripts/doctor.sh --json`. It queries live tools/device/storage/MCP and checks the recorded smoke result; it never depends on proprietary game files. Exit zero means all configured checks pass. Nonzero is expected until installation and acceptance finish.

## Outstanding work / authentication

See `auth-notes.md`. Unity Hub sign-in is not yet confirmed; an existing local license must be validated with the editor. Finish installing, run the build/device acceptance loop, connect/test Unity MCP, refresh this report and version records, and commit/push the reviewed non-secret artifacts. Agent #2 must not begin the port until bootstrap acceptance is complete.

## Sources

- Unity archive: https://unity.com/releases/editor/whats-new/2021.3.33f1
- Hub CLI: https://docs.unity.com/en-us/hub/use-hub-cli
- Codex MCP configuration: https://learn.chatgpt.com/docs/extend/mcp?surface=cli
- Unity MCP: https://github.com/CoplayDev/unity-mcp/tree/v10.2.0
- AssetRipper: https://github.com/AssetRipper/AssetRipper/releases/tag/2.0.0
- Turnip target: https://github.com/MrPurple666/purple-turnip/releases/tag/vturnip_mrpurple_T30-toasted.adpkg
- Valve SteamCMD: https://developer.valvesoftware.com/wiki/SteamCMD
