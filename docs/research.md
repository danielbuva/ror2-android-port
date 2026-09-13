# Research ledger

Checked 2026-09-12 PDT. Local installation evidence outranks assumptions about other releases. VERIFIED means measured in this input/tool/device; INFERRED means a supported conclusion not yet exercised; UNVERIFIED means no adequate evidence; EXPERIMENTAL means a deliberately narrow prototype, not game readiness. A native library's presence is not proof its initialization path executes.

| Primary source | Relevance and limits |
| --- | --- |
| [Unity 2021.3.33f1](https://unity.com/releases/editor/whats-new/2021.3.33f1) | Exact editor revision ee5a2aa03ab2; local player header and editor agree. |
| [Unity scripting restrictions](https://docs.unity3d.com/2021.3/Documentation/Manual/ScriptingRestrictions.html) | Android IL2CPP is AOT. Runtime-generated IL needs another approach; importing existing DLLs as build inputs is distinct from dynamically executing them after installation. |
| [Building AssetBundles](https://docs.unity3d.com/2021.3/Documentation/Manual/AssetBundles-Building.html) | Explicit build target and compression matter. Build Android bundles locally; do not relabel Windows bundles. |
| [Unity persistentDataPath](https://docs.unity3d.com/2021.3/Documentation/ScriptReference/Application-persistentDataPath.html) | Android runtime supplies an app-specific files path. Query actual device backing separately. |
| [Android install location](https://developer.android.com/guide/topics/data/install-location) | Manifest install preference is not a placement guarantee. |
| [AOSP adopted storage](https://source.android.com/docs/core/storage/adoptable) | Private adopted volumes can hold apps and data. Device live state remains authoritative. |
| [AssetRipper 2.0.0 source](https://github.com/AssetRipper/AssetRipper/tree/2.0.0) | Inspected WebApplicationLauncher and Pages/Commands source: local form POST APIs LoadFolder and Export/UnityProject. Default export preserves many managed DLLs and emits dummy shaders. |
| [ILSpy](https://github.com/icsharpcode/ILSpy) | Local ilspycmd 11.0.0.9375 help verifies project export, reference path and CSharp9_0 selection. |
| [UnityPy](https://github.com/K0lb3/UnityPy) | Pinned 1.25.3; local public loader, typetree reader and Mesh.export used. |
| [Wwise Unity integration](https://www.audiokinetic.com/en/public-library/edge/?id=index.html&source=Unity) | Managed bindings plus native sound engine; current documentation does not establish permission to redistribute the game's matching middleware. |
| [Wwise SoundBank platforms](https://www.audiokinetic.com/en/library/2024.1.0_8669/?id=pg_customplatforms.html&source=Unity) | Platform resolution selects a bank directory. A directory rename does not convert encoded bank content. |
| [Wwise licensing](https://www.audiokinetic.com/download/documents/License_Agreements/Audiokinetic_SDK_Agreement_v3_2024-07-30.pdf) | Licensing/redistribution must be resolved with the vendor; game ownership alone is not treated as an SDK redistribution grant. No licensed SDK acquired in this task. |
| [Rewired supported products/platforms](https://guavaman.com/projects/rewired/) | Android is supported by the product. This does not establish that the Windows-compiled managed subset is a complete Android integration. |

No Steam login, ownership emulation, entitlement patch, DRM bypass, EOS authentication emulation, or original-install modification was performed. SDK licensing and exact legacy Android binary availability remain explicit backlog items.
