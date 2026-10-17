# Platform compatibility matrix

GREEN = demonstrated compatible or safely unnecessary for this isolated lab. YELLOW = adaptation path identified. RED = unavailable/replacement/licensed runtime needed. UNKNOWN = insufficient evidence. Status for the isolated lab must not be mistaken for status of the game.

| Dependency | Status for full game | Evidence and next boundary |
| --- | --- | --- |
| Unity Android player / IL2CPP ARM64 | GREEN baseline | Bootstrap passes on real device; instrumented lab extends this. |
| RoR2.dll and dependency closure | YELLOW | Mono IL available; full exported closure AOT attempted and blocked by Rewired VTable conflicts. Source recompilation has measured blockers. |
| Wwise engine | RED | Windows x86_64 2023.1.4.8496. Need legitimate compatible Android ARM64 runtime and permitted redistribution model. |
| Wwise banks/codecs | UNKNOWN | Windows banks, format 150. No Wwise authoring project proven present. Regeneration may require unavailable authoring sources; codec/platform compatibility must be measured. |
| Rewired | RED in current closure | Core 1.1.47.0.U2021; official Android support exists, supplied native DLLs are Windows only. Licensed Android package or input adapter required. Minimal Android build hits duplicate override/VTable definitions in Rewired_Core and Rewired_Windows. |
| Steam / Facepunch | RED startup dependency | Steam initialization, identity, save, achievements and entitlements. Do not emulate or falsify entitlement/ownership checks. |
| EOS 1.16.1 | RED/UNKNOWN | Windows binaries and login/network integration. An offline experiment must avoid login-dependent paths, without claiming authentication success. |
| Discord | UNKNOWN | Native binary present; initial metadata search does not establish a gameplay requirement. Verify call sites before making no-op adapter. |
| HLAPI / local authority | YELLOW | Network manager is instantiated during startup even before a solo run. Retain local simulation semantics; defer remote transport. |
| PlayFab Party / Multiplayer / Xbox bridges | UNKNOWN/RED if reached | Windows binaries; no Android runtime here. Reachability analysis precedes any service replacement. |
| Sony platform managed libraries | UNKNOWN | Shipping residues and references; remove only after dependency/serialization evidence. |
| Burst / Collections | RED editor compatibility | Recovered player assemblies crash editor Play Mode in BurstCompilerService direct-call initialization; compatible editor/package replacement is unproven. |
| Zio / filesystem | YELLOW | Current dataPath-based physical filesystem must be separated into content/save roots. |
| Windows PE native libraries | RED | None can be loaded as Android ARM64 ELF libraries. |
| SimpleJSON preserved assembly | GREEN for tested subset | JSON parsing is the lab's AOT preservation checkpoint. |

## Wwise startup and no-audio boundary

VERIFIED static order in RoR2Application.OnLoad: enable startup behaviors → WwiseIntegrationManager.Init → Addressables.InitializeAsync → PlatformSystems.Init → Steam callback → RewiredIntegrationManager.Init → instantiate network manager → platform network initialization. Async behavior can overlap; this is call ordering, not an observed runtime timeline.

WwiseIntegrationManager loads WwiseGlobal through LegacyResourcesAPI, which creates/uses AkInitializer. Initialization checks, PostEvent, bank loads, RTPC, switches/states and object registration are among the managed API seams. `AK.Wwise.Unity.API.dll` contains 1,279 imports; source references and metadata are available locally. Audio absence must cover object lifecycle and callbacks, not just one Init function. A no-audio bootstrap is INFERRED feasible; actual RoR2 lifecycle behavior remains UNVERIFIED. The lab intentionally does not initialize Wwise.

Native version is VERIFIED 2023.1.4.8496. Exact managed integration package build is UNVERIFIED; compatibility is inferred from shipping together. Windows bank metadata declares version 150. Do not assume renaming the bank folder converts content, that all codecs are platform neutral, or that a current Wwise engine reads every old bank. Ask for vendor licensing/auth only when an actual compatible SDK acquisition is needed.

## Rewired and controller-first boundary

RoR2 loads a serialized Rewired Input Manager prefab, subscribes controller connect/disconnect events, assigns controllers to Rewired players and initializes UI maps. Android support from the vendor makes a controller-first path plausible. Preserving gameplay input queries requires retaining player IDs, action IDs, category/layout maps and controller assignment semantics. Windows DirectInput/WindowsGamingInput imports cannot serve the handheld. The lab reports Unity joystick enumeration; that does not validate the original Rewired mappings.

## Platform services and offline scope

Use an explicit development capability model: optional presence/social/remote transport may be unavailable; mandatory entitlement/authentication remains a distinct unresolved gate. No patch in this repository claims Steam or EOS authentication succeeded. Do not turn failure into owned/unlocked status. Plan the legally valid offline entry point and preserve legitimate content entitlements before attempting a game startup adapter.

For solo gameplay, retain NetworkServer/NetworkClient and authority behavior as required by the game; defer external matchmaking, remote peers and voice. EOS branches still coexist with Steam-backed save/achievement/entitlement selection in this build, so an EOS flag is not a complete offline solution.

Additional static reachability audit: no DllImport declarations target Discord, PlayFab or PartyXbox libraries in the 143 managed assemblies. Discord string hits resolve to EOS account/credential enum members and social-icon Addressables keys, not a discovered Discord SDK startup call. Thus Discord exclusion is INFERRED low risk for the offline lab, but whole-game absence is not proven by text search. PlayFab/Party binaries remain shipping-residue candidates until indirect/native/dynamic loading is ruled out. Evidence: `work/inventory/middleware-reachability.json` plus local decompiled references. No Wwise `.wproj` or `.wwu` authoring sources are present in the inventoried installation, so bank regeneration is not currently reproducible from those files alone.
