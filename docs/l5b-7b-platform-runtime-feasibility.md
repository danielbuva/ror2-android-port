# L5b-7b — legitimate platform-runtime feasibility

Date: 2026-09-19 PDT. This is a read-only feasibility experiment following J60; it does not change an assembly, package, payload, device, original installation, or Steam configuration.

## Observation

J60's first, fresh-process construction reaches `SteamNative.Platform.Win64.Native.SteamAPI_Init` and fails to resolve `steam_api64.dll`. The failure occurs before the original manager can call its Steam API validator or `App.IsSubscribed`, so it is not ownership evidence.

The exact preserved `Facepunch.Steamworks` input has no Android/ARM64 platform implementation. `SteamApi` selects only Win32, Win64, Linux32, Linux64, or macOS. Its platform fallback treats an unrecognised runtime as Windows, while architecture is reduced to x86/x64 by pointer size; Android ARM64 is not representable. The selected Win64 implementation imports `steam_api64.dll`. `NativeInterface.InitClient` requires a successful `SteamAPI_Init`, nonzero pipe, and valid user before the original `SteamworksClientManager` can reach its own validator and subscription checks.

The original manager then requires a valid client, `RestartIfNecessary`/validator checks and `App.IsSubscribed(632360)` before assigning Steam remote storage. `PlatformSystems.Init` installs the Steam save, achievement, and entitlement systems even on its EOS branch. Thus changing an OS/backend string, substituting a Linux library, or returning invented client values would not be a lawful compatible integration.

## Prior art and authoritative documentation

The pinned `NextBep/BepInEx.Android` source at `33c989e9099f` documents an Android IL2CPP/CoreCLR bootstrap through `libfusion.so`; it contains no Steam/Facepunch implementation. Its launcher at `fd1a4023fa2f` is a mod-injection/runtime-container project, not a Steam client or entitlement implementation. Per `docs/community-prior-art.md`, this is post-vanilla tooling and is not an adapter candidate.

Valve's current Steamworks API documentation lists the ordinary redistributables as Windows `steam_api[64].dll`, macOS `libsteam_api.dylib`, and Linux `libsteam_api.so`; it requires a successful `SteamAPI_Init` before interfaces are used and lists a running Steam client, App ID and current-account license among its prerequisites. Valve's newer Steam Frame documentation separately describes an Android route: a Steamworks partner configures Android support, an Android depot, an APK launch option, package access, and (if used) Android cloud storage. That is an authorized publisher-side integration route, not a compatible runtime supplied to an arbitrary Android device.

Sources: [Steamworks API Overview](https://partner.steamgames.com/doc/sdk/api), [Steam Frame Android APK deployment](https://partner.steamgames.com/doc/steamhardware/steamframe/apk_upload).

## Result — access and compatibility blocker

No legitimate compatible runtime or authorized integration is established for the accepted Windows input on the current Android device:

- The preserved managed binding has no Android ARM64 selector or ABI contract.
- The lab has no authorized Android Steam runtime, Android depot, Android launch path, or publisher-side Steamworks access for this app.
- The generic authorized Android device is not a Steam Frame/Lepton environment, and a desktop ownership record cannot create an Android authenticated Steam context.
- Even a future publisher-approved Android delivery would require a compatible ARM64 native library and an intentionally authored/authorized binding integration, then fresh tests of client initialization, App ID delivery, account/license, subscription, remote storage, callbacks, and entitlement behavior. It cannot be validated by copying a desktop DLL or altering a selector.

Therefore L5b-7b completes as a negative feasibility result. L5 remains open and dependent original startup/menu, original profile flow, and L5.5 simulation remain stopped at the platform boundary. No device probe is justified because there is no candidate runtime to test.

## Revisit condition

Reopen only if the rights holder grants a concrete Android Steamworks/Steam Frame integration route for this app, including the compatible ARM64 runtime and authorized depot/launch configuration, or if an authorized product architecture supplies an independently lawful entitlement path that preserves the original mandatory checks. Before any implementation, re-audit the exact binding and platform contracts; do not treat a changed backend string or a successful stub as evidence.
