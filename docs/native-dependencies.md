# Native inventory

VERIFIED from PE machine headers and import tables. The one x86 EOS SDK binary is inside a directory named x86_64: directory labels are not architecture evidence. No installed game native library is an Android ELF ARM64 binary.

| Binary family | Version evidence | Android implication |
| --- | --- | --- |
| UnityPlayer, executable, crash handler, Mono runtime/helper | Unity 2021.3.33f1 / x86_64 | Replace with editor-generated Android player and IL2CPP runtime. Never copy Windows runtime into APK. |
| AkSoundEngine | **2023.1.4.8496** | Exact version verified by PE export trampolines and immediate integer return values; Windows SDK strings independently mention 2023.1. Need compatible licensed Android engine. |
| EOSSDK-Win64/Win32-Shipping | **1.16.1-27379709** | Windows x86_64/x86. Android SDK integration and service policy unverified. |
| Rewired_DirectInput, Rewired_WindowsGamingInput | Managed counterpart 1.1.47.0.U2021 | Windows controller backends; use a lawful Android-capable integration or bounded input adapter. |
| steam_api64 | Source control ID 4285107; generic file version 1.0.0.1 | Windows Steam API; Android offline lab must not emulate ownership/authentication. |
| discord_game_sdk | Version not established | Optional integration reachability unknown. Disable optional rich presence only if call graph shows it is safe. |
| PlayFab Party | 1.7.11 | Windows transport/voice; defer online features, inspect startup reachability. |
| PartyXboxLive | 1.2.10 | Xbox identity bridge; no ARM64 Android binary in input. |
| PlayFabMultiplayer Win/GDK | 1.3.0 | Windows/GDK networking; inventory does not establish it runs in solo play. |
| XCurl | 2106.4.0.0 | Windows Xbox HTTP wrapper. |
| xaudio2_9redist | 1.0.0.1 | Windows audio runtime; cannot load on Android. |

Evidence: `work/inventory/native.json`, all P/Invokes in `managed.json`, version-return bytes and source hash in `middleware.json`. Native compatibility has not been inferred merely from a managed DLL compiling.
