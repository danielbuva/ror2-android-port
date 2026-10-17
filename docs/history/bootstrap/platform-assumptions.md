# Platform assumptions and uncertainty

| Claim | Status | Evidence / next test |
| --- | --- | --- |
| Windows Mono, Unity 2021.3.33f1 | VERIFIED | Player headers, Managed directory and AssetRipper import log. |
| Built-in deferred / linear pipeline | VERIFIED settings; INFERRED active default | Serialized GraphicsSettings; inspect per-camera runtime overrides later. |
| Windows bundle/shader portability | VERIFIED platform mismatch | Serialized target and shader compiler platform; device shader probe supplies narrower runtime behavior. |
| Steam services initialize before ordinary gameplay | VERIFIED static startup | RoR2Application → PlatformSystems.Init → SteamworksClientManager.Init. Runtime reachability not yet traced in RoR2. |
| EOS replaces every Steam assumption when enabled | Rejected assumption | PlatformSystems retains Steam save/achievement/entitlement services even around EOS branches. |
| Single-player needs no networking code | Rejected assumption | Startup creates a network manager; local authority/run simulation uses HLAPI semantics. |
| Original source platform conditionals can be recovered | Rejected assumption | Only the compiled Windows branches are available. |
| Existing Wwise banks work on Android | UNVERIFIED | Windows platform, bank version 150; test only with compatible licensed runtime and codecs. |
| Every Unity resource can live in a separately synced folder | Rejected assumption | Player data/initial scene and AOT code remain coupled to APK. Explicit bundles and redirected providers are candidates. |
| Precompiled DLL import avoids IL2CPP/AOT | Rejected assumption | DLLs remain build inputs and become native code. Dynamic IL loading/Reflection.Emit remains restricted. |
| Original RoR2.dll can be preserved wholesale | EXPERIMENTAL | SimpleJSON preservation is a narrow prerequisite, not a RoR2 AOT result. |
| Custom Turnip driver active | UNVERIFIED | Bootstrap only staged driver archive. Runtime logs must identify selected API/driver. |

Save/config: startup roots a Zio PhysicalFileSystem/SubFileSystem at Application.dataPath; Steam cloud/save abstractions appear in PlatformSystems. Android dataPath may address packaged content rather than a writable directory. Introduce an explicit runtime content root and app-specific save root; do not rewrite the user's existing Steam save/profile.
