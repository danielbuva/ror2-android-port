# RoR2 community prior art at the L5a boundary

## Purpose and evidence rules

Keep DEVELOPMENT_PLAN.md and Architecture C authoritative. This reference prevents rediscovery of RoR2 mechanisms; it does not introduce a mod host, change the editor/packages, or advance a capability gate. Inspected 2026-09-13 UTC / 2026-09-12 PDT at `3cfc3a4f5375da72fb89ad648cae813e77f57612`.

Evidence order: measured legitimate input → local experiments → exact community source → Risk of Thunder documentation → functioning mod projects → issues/PRs → conversation leads. **VERIFIED** identifies either a stated source implementation or measured local fact, explicitly scoped. **INFERRED** is a supported applicability judgment. **EXPERIMENTAL** requires a new test. **NOT APPLICABLE** rejects use at this boundary. A community package version is never evidence of the shipped game's package version.

The [structured source index](../reference/community-sources.json) records 16 repositories, exact inspected SHAs, file permalinks, licenses, commit activity, version assumptions, reuse boundaries and milestones. Source IDs below resolve through that index. Public reference checkouts are shallow, source-focused and ignored under `work/reference-repos/`; nothing is installed in Unity or the game. No source code was copied into authored implementation. A root license does not grant rights to bundled game declarations, assets or proprietary middleware.

## Verified baseline and version caveat

**VERIFIED, local:** expected HEAD matches; inventory records app 632360/build 21587608 and editor 2021.3.33f1. The archived L4 stage's 45 DLL hashes match its original-input manifest; the accepted APK matches its SHA-256. L3's full-original trajectory/proc assertions and L4 scene/rig/pose reports remain historical device evidence, not new executions. J11/J12 original Rewired slots and J13/J14 representative Burst/Collections proofs remain accepted. Tested package tuple remains Burst 1.8.11 / Collections 1.2.4 / Mathematics 1.2.1.

The recovered input ProjectSettings records `bundleVersion: 1.4.1`; this is an exported setting, not a newly observed stock runtime version string. Its path is `work/assetripper/53efd194cd207e66/export/ExportedProject/ProjectSettings/ProjectSettings.asset`. Original RoR2 decompilation receipt `work/decompiled/RoR2/0993a9f3fcd8540d/result.json` matches DLL hash `0497a902a7aaf3c97fa2f1251a5364723b0c1b422839f7002a4b5f9c02563e4f`. Local source references below are in that directory; they stay ignored.

**VERIFIED, community:** R2Wiki's current Extraction page mentions 2021.3.33.23082 for Alloyed Collective, while Starstorm2's ProjectVersion explicitly records our 2021.3.33f1 revision. EditorKit 5.7.0 declares Unity 2021.3 and currently selects a bundled mapping labeled 1.4.1. Matching a version label does not establish identical GUID/type/catalog contents. Do not replace the exact local editor or accepted package tuple.

## Asset extraction and reconstruction

R2Wiki distinguishes post-SOTS dummy shader export from older YAML shader workflows. Its Code Analysis and Source Code Diff pages explain ILSpy/IL inspection and deterministic attribute ordering for update diffs. **INFERRED reuse:** these corroborate using exact-input code and explain why old shader tutorials cannot repair our D3D11 payloads. No new extraction or source-diff engine is needed; our input receipts and decompilation already cover this boundary. Older LightingData/UI-DLL advice is version-specific and must not trigger cache deletion or provider replacement.

RoR2ImportExtensions conditionally excludes the shipped HLAPI/postprocessing DLL when corresponding packages provide it, avoiding duplicate providers. It offers publicizer and MMHook generation steps, deferred shading, and specific addressable graphics keys. **NOT APPLICABLE now:** publicizing the unchanged DLL set or generating Mono runtime hooks. The applicable concept is measured, single-owner assembly provision; our passing 45-DLL recipe remains intact.

ThunderKit's `ImportAddressableCatalog.Execute` copies catalog/settings to `Assets/StreamingAssets/aa`. It neither derives Android locations nor converts Windows bundles. Its graphics importer and browser can help inspect desktop authoring state, but adding ThunderKit is unnecessary for L5a. Source license is MS-PL, not MIT.

## Addressables/catalogs: what is already solved

**VERIFIED, EditorKit source:** `AddressablesPathDictionary` supports path↔GUID and type lookup from JSON, including collision handling. The current `GetLRAPIReturnsJsonData` deliberately selects its bundled 1.4.1 table; the ordinary game-file path is commented out. `AddressablesPathDictionaryCache` keys type/component plus child-search policy, rebuilds empty hits, and keeps per-user project state. Component-restricted queries actually load GameObjects and inspect their components; these are not read-only catalog decoding. Subasset selection uses a bracket-key heuristic and often location index 1; missing locations fall back to table type metadata. Those are useful known edge cases, not a universal identity algorithm.

**Decision:** retain our original `ContentCatalogData.CreateLocator` and measured imported fileIDs. Cross-check against the legitimate `lrapi_returns.json` when needed; do not copy the community's table or accept its fallback type as proof that an asset exists. Preserve `(runtime key, requested type, subobject, provider, internal ID, dependency identity)` together. Never pick the first location solely because a GUID matches. Do not turn an empty lookup into a permanently cached successful absence.

**VERIFIED, R2API source:** `AddressReferencedAsset<T>` is a mod wrapper, distinct from the game's `AssetOrDirectReference<T>`. It checks locations, holds async handles, supports coroutine/synchronous paths, releases on address change, and records failure. Some specialized wrappers can resolve game catalogs and therefore depend on catalog readiness. In this inspected revision `OnAddressReferencedAssetsLoaded` is obsolete and invoked on `RoR2Application.onLoad` for compatibility; it is not a reliable all-assets-loaded barrier. Check actual completion/status rather than adopting that event name as an assertion.

The wiki's Addressables Assets Keys page links a generated public dump and generator; its Prefabs page documents live inspection. These are cross-checks with no demonstrated equality to build 21587608. We did not download a proprietary dump. Existing local typed catalog queries are sufficient for the first asset; a new global catalog/dump service is unnecessary.

## Skin/content loading: current-input authority

The community [1.3.9 memory-update guide](https://risk-of-thunder.github.io/R2Wiki/Mod-Creation/Updating-Your-Mods/1.3.9-Memory-Optimization/Core-API-Changelog-1.3.9/) identifies deferred skin data, animator/avatar references, typed GUID requests, preload policies and startup-phase attributes. **VERIFIED locally:** those named classes and mechanisms exist in our input. This explains J25's intentionally empty prefab fields; it is not evidence of incomplete extraction.

Local `ModelSkinController.animatorControllerRef` constructs `AssetOrDirectReference<RuntimeAnimatorController>` with `loadOnAssigned=false`, prefers a valid address and otherwise uses its legacy direct field. `Awake` requests animator assets unless delayed; `Start` selects an unload lifetime based on player/run state and starts `ApplySkinAsync`. `OnDestroy` resets references and unloads skin assets. Full component activation would add several variables, so do not use it as the first provider test.

Local `SkinDef.BakeAsync` loads `SkinDefParams`, constructs runtime renderer/mesh/activation templates, and releases the parameter reference. Runtime application requests materials/meshes/other objects and applies them to the model. The six manually bound J26 assets prove content integrity, not this lifecycle.

Local `AssetOrDirectReference<T>.LoadAsync` delegates to `AssetAsyncReferenceManager<T>.LoadAsset`; `Reset` delegates unload. Within each closed generic T, the manager keys by `reference.RuntimeKey.ToString()`, shares handles and tracks its own counts/lifetime priorities. `AtWill` unload decrements a count and schedules expiry five seconds later; periodic cleanup calls Addressables.Release. Its static constructor subscribes to `RoR2Application.onUpdate` and scene changes. With application startup inactive, that update event does not run automatically. Its logging convar reaches `NetworkPreloadManager`; no native service call was found on this narrow path, but device initialization still requires testing. Completion callbacks can receive a null result on failure: assert status and result, not callback occurrence alone.

**Real implementations:** Starstorm2's `SS2VanillaSurvivor.LoadContentAsync` awaits its asset collection and a SurvivorDef request. `InitializeAsync` prebakes MSU UberSkinDefs, then adds skins to both body and display ModelSkinControllers. MSU's old VanillaSkinDef is explicitly obsolete. RoRSkinBuilder's current generated plugin creates SkinDefParams and fills renderer/mesh/activation structures, with desktop shader substitution. R2API.Skins also checks body/display skin agreement late at main-menu initialization. These illustrate content contracts and reveal stale tutorials; none proves Android loading or justifies copying stock assets/entitlement adjustments. Starstorm2 contains a temporary entitlement-related script: **NOT APPLICABLE**, not a port adapter candidate.

## First L5a device experiment recommendation

### Observation and hypothesis

**OBSERVATION — VERIFIED local:** controller GUID `48ef8327759dd43439416d4823124d9c` resolves to `animCommando.controller`; our local Android prefab bundle already contains its recovered equivalent with 35 clips including RunForward. Original startup is inactive; current explicit binding never exercises the original request/handle path. Windows catalog closures contain over 1,000 dependencies and cannot be reused as an Android manifest.

**COMMUNITY PRIOR ART:** EditorKit supplies lookup edge cases; R2API distinguishes asynchronous handles from catalog-ready events; the wiki and real skin projects identify the game's typed deferred-reference system. Our original Addressables/ResourceManager source supplies the actual runtime provider contract.

**HYPOTHESIS — EXPERIMENTAL:** a tiny local catalog/location mapping plus the existing original `AssetBundleProvider` and `BundledAssetProvider` can serve this one typed request without changing RoR2 methods or activating game startup.

### Ranked candidates

| Order | Candidate | Fidelity / preserved code | Surface, future compatibility, Android/update tradeoff |
| --- | --- | --- | --- |
| A first | Minimal local initialization settings/catalog and typed locator entry using existing bundle providers | Preserves original game wrapper, manager, async handles, providers and release semantics | A few generated locations/settings; original key maps to measured Android bundle/internal path. Reusable for later assets. Must validate original provider options and initialization schema; Android is unproven. |
| B fallback | Same typed locator, narrow custom provider wrapping the receipted Android bundle | Preserves game caller/manager and ResourceManager operation protocol | More authored completion/failure/release/wait behavior to maintain. Justified only by a measured built-in-provider limitation. Never return synthetic success for absent content. |
| C later | Rebuild a wider Android Addressables catalog using a matching authoring pipeline | High potential semantic fidelity | Larger package/catalog build surface and runtime schema compatibility burden. Appropriate when actual content breadth requires it, not one asset. |
| Rejected for this proof | Patch original LoadAssetAsync / direct-reference assignment / relabel Windows catalog | Omits the very semantics under test or retains invalid platform payloads | Repeats L4 binding or creates broad hooks. Does not pass L5a provider acceptance. |

**WHY A FIRST — INFERRED:** the original BundledAssetProvider already handles typed async bundle asset requests, named subobjects, completion/failure and dependency loading; AssetBundleProvider handles bundle release. We should test that existing implementation before writing a replacement. This recommendation is contingent on constructing a valid tiny initialization recipe, not a claim it already works.

**ORIGINAL METHOD TO EXERCISE:** `RoR2.ContentManagement.AssetOrDirectReference<UnityEngine.RuntimeAnimatorController>.LoadAsync()`, using an `AssetReferenceT<RuntimeAnimatorController>` copied from the inactive ModelSkinController address, `loadOnAssigned=false`, unload policy `AtWill`. It calls original `AssetAsyncReferenceManager<RuntimeAnimatorController>.LoadAsset`. Do not assign `directRef`. Preserve all 45 original DLL hashes and the required generic/reflection roots.

**INPUT:** runtime GUID above; requested type RuntimeAnimatorController; output internal asset path measured in the existing Android bundle (`Assets/LabLoadingScene/RoR2/Base/Characters/Commando/animCommando.controller`, verify actual bundle asset-name normalization before use). Use the accepted bundle hash/manifest from J28 and discover its live app-owned path. Register the canonical address alias only if verified from the current catalog. Start with controller because it avoids the FBX subobject ambiguity of avatar/meshes.

**EXPECTED RESULT:** successful typed handle, recovered controller identity and 35 expected clips including RunForward. No normal skin application, character state or platform readiness is implied.

**LIFECYCLE:** explicitly initialize original Addressables against a small owned local settings/catalog recipe; register only the measured typed location and its Android bundle dependency. Adding a locator alone is insufficient: this input's first LoadAssetAsync chains Addressables initialization, which otherwise reads default settings. Do not set private initialization flags to pretend success. Keep this bundle exclusively provider-owned in the probe; avoid loading the same bundle through the old explicit-binding harness as well. Make two wrapper requests, assert shared handle/result, release one and verify the other remains valid, then reset the second. For a bounded release test while startup is inactive, explicitly tick the preserved original manager's private `Update` via a narrowly rooted diagnostic invocation and observe expiry over at least 10 seconds. Record this harness-supplied scheduler distinctly; it does not prove normal game-loop integration. If reflection/AOT access is unavailable, classify that first; do not activate the whole application to obtain a tick. Check the old handle becomes invalid and the owned bundle is released, then reload. Run missing-key and wrong-type controls through Addressables directly to isolate locator/provider failure semantics from the game manager cache; expect failure, never a valid substitute.

**PLATFORM SERVICES REQUIRED:** INFERRED no Steam/EOS/Wwise/ReInput for this narrow controller request. Local static subscriptions/convar initialization and Addressables initialization remain measured risks. **PROFILE REQUIRED:** INFERRED no; no save system is initialized. Keep profile/content roots distinct for later startup.

**DEVICE PASS CONDITION:** current attempt/PID, ARM64, unchanged original DLL hashes, successful real initialization, typed location/provider/internal ID and Android payload identity, correct controller/clip results, repeated-handle behavior, release/reload and negative controls, at least 30 seconds alive, no unexplained managed/native failure, owned cleanup. Any visual reuse is corroboration only. This passes one provider assertion, not L5, full skin loading or L5.5.

**FAILURE CLASSIFICATION:** initialization/settings/schema → key/type/subobject identity → provider/dependency/bundle target → asset deserialization/AOT → callback/status/cache → scheduler/reference count/release → unexpected native/platform initialization. Preserve the first failed attempt; choose B only if A's provider limitation is demonstrated. Follow with avatar subobject identity and SkinDefParams/BakeAsync as separate issues after the controller lifecycle passes.

## Startup/platform graph and profile boundary

**VERIFIED static trace, not device execution:** local `RoR2Application.InitializeGameRoutine` follows this backbone. Phase callbacks and content coroutines mean this is not a total-order graph of every initializer:

`PreFrame attributes → loadingbasic wait → EnableBehaviours → WwiseIntegrationManager.Init → Addressables.InitializeAsync → filesystem roots → PlatformSystems.Init → loadSteamworksClient delegate → RewiredIntegrationManager.Init → UI event system/network manager → text config/Console → sound-engine query/language/shaders → PreSplash → concurrent content loading + camera/splash/menu loads → platform manager/voice → SystemInitializer/DuringIntro → achievements/logbook → EntityStateCatalog → LocalUserManager → Steam failure dialog OR profile load → onLoad/PostProgressBar`.

`LoadGameContent` registers content-pack providers and runs ContentManager phases. R2API's provider mirrors LoadStaticContentAsync / GenerateContentPackAsync / FinalizeAsync. Content-pack registration and catalog readiness are real seams; BepInEx's Awake and a mod's onLoad hook are not substitutes for those game phases.

| System | Local-simulation classification | Current-input consequence |
| --- | --- | --- |
| Typed content, required catalogs, EntityStateCatalog | MANDATORY FOR LOCAL SIMULATION | Populate required identities before body/state use. Full catalog breadth unmeasured. |
| Master/body, HLAPI identity/server/client authority | MANDATORY FOR LOCAL SIMULATION | Offline play does not remove network authority semantics. |
| Local user/profile/loadout + input mapping | MANDATORY for intended local player flow | Fresh isolated profile foundation before menu; not required for the one controller request. |
| Steam/EOS lobby, presence, remote peers | PLATFORM/ONLINE role | Their purpose differs from simulation, but current startup invokes concrete implementations; removability remains UNKNOWN. |
| Entitlement resolver/authenticated identity | UNKNOWN lawful offline boundary | Preserve mandatory checks. No unavailable result becomes owned/authenticated. |
| Wwise/native sound | OPTIONAL product capability, UNKNOWN startup separation | Init occurs early; later sound query catches a native-library failure. No-audio requires measured lifecycle handling, not only removing one call. |
| ReInput | MANDATORY eventual handheld/input flow | Original slots passing does not prove controller initialization or native backend support. |
| Console/config/language/UI shaders | MANDATORY for original startup/menu route | Deferred content and writable paths need separate observations. |

Local `PlatformSystems.Init` starts Steamworks handling even around the EOS selection path; it installs SaveSystemSteam, AchievementSystemSteam and SteamworksEntitlementResolver. Flipping the EOS flag is not an offline adapter. Do not classify stock startup's service calls as harmless because a mod runs after them.

**Profiles — VERIFIED static:** UserProfile has SaveField-driven serialization, loadout/stats/unlockables and an IFileSystem reference. SaveSystem uses `/UserProfiles/*.xml` relative to `RoR2Application.cloudStorage`; SaveSystemSteam reads/writes XML through that filesystem. The bootstrap initially roots files under Application.dataPath, while SteamworksClientManager replaces cloudStorage with SteamworksRemoteStorageFileSystem. Thus a path name or a serializer alone does not prove local/cloud separation. Android must provide an owned writable profile root distinct from read-only converted content and never point these abstractions at the host Steam directory. Save copy/serialization, interrupted writes and RunReport/history acceptance remain L9 work; this research performs no save operation. Community skin documentation's profile-backup warning supports isolation, not importing or editing existing saves.

**VERIFIED, ProperSave source:** version 3.0.7 selects either RoR2Application.cloudStorage or a PhysicalFileSystem/SubFileSystem rooted at persistentDataPath (or an explicit directory). Its save header links to the local UserProfile filename. This is concrete prior art for separating filesystem policy from serialization. Its mod run-save format is not vanilla profile XML, and its cloud-storage mode is not an Android ownership solution. No license file was found in the inspected tree; learn the boundary without copying implementation.

## Future subsystem map

| Subsystem | Prior art and exact useful boundary | Port consequence |
| --- | --- | --- |
| Character / EntityStates | Starstorm2 SS2VanillaSurvivor links named EntityStateMachines into NetworkStateMachine and death/hurt lists; R2API content packs register state types | L5.5 must preserve these relationships; adding an Animator alone is not simulation. |
| Networking/authority | R2Wiki UNet reference; R2API.Prefab registration/NetworkIdentity; DebugToolkit server guards and master queries | Query actual NetworkUser/master/body and server authority, not object names. No remote multiplayer or hook host added. |
| Directors/stages/combat | R2API.Director stage selection/event seams; Starstorm2 SlateMines scene content; DebugToolkit SceneCatalog/Run queries | L6/L7 use known catalogs/pools for observation. Spawn/teleporter/debug commands cannot establish normal stage completion. |
| Items/damage/language | R2API module boundaries | Consult exact module when that milestone begins; no speculative integration or blanket module compatibility claim. |
| Input | Local RewiredIntegrationManager and R2Wiki networking/user conventions | Preserve action/player/map identities. No inspected community source establishes our Android ReInput backend. J11/J12 not reopened. |
| Burst/Collections | ThunderBurster dependency installer and CollectionsEmbedder; BurstsOfRain AddBurstAssembly | Installer tuple is 1.8.18/1.5.1/1.2.6; embedder adjusts CodeGen constraints and removes a Mono.Cecil package dependency for BepInEx coexistence. BurstsOfRain loads additional native libraries using .dll paths. These solve mod-host issues, not our original ARM64 problem. Keep J14 tuple. |
| Graphics | EditorKit YAML shader registration; ImportExtensions custom deferred shader paths; wiki extraction split | RegisterShader fixes editor discovery, not D3D11→Vulkan translation. Keep diagnostic shader acceptance scoped; future material families need Android programs. |
| Wwise | R2API.Sound wraps native bank registration/loading; wiki memory guide describes staged banks; SS2 has Wwise source/settings | Event/bank lifetime is useful prior art. No Android SDK/bank/codec permission or ABI proof follows from source availability. |
| Diagnostics | DebugToolkit Util/NetworkManager/AutoComplete; UnityExplorer and wiki Prefabs | Adapt read-only semantic observations into our harness. Avoid broad mutation commands and account-name capture. |

**Starstorm2 configuration trap:** Unity `m_Enabled: 1` does not mean an OptionalExecutor is selected. In the inspected ImportConfiguration, MMHook Generator, Assembly Publicizer and Wwise Blacklister each have `enabled: 0`. They are configured capabilities, not evidence those transformations ran. Its manifest uses newer Burst/Collections, community HLAPI, MSU and a particular ThunderKit/editor-kit/importer tuple. Preserve our passed set instead of copying the manifest. Its real content classes normalize asset collections, async content loading and body/display skin registration; Android retargeting and native dependencies remain separate.

## Optional desktop reference execution

**INFERRED useful, not required now.** The environment report records a legitimate installation in CrossOver on this ARM64 Mac. That proves presence, not that stock execution currently works. No desktop game or inspector was launched, and no original installation was changed.

If the controller test has ambiguous lifecycle behavior, the smallest reference capture is one typed controller load/completion/release trace with runtime key, provider/internal ID, handle status, elapsed release timing and current scene. Use a separately isolated legitimate reference setup if feasible, with a small read-only diagnostic; do not modify the original installation to install tools. UnityExplorer can inspect objects but alters the process; R2Wiki even records an overlay/lobby interaction. Call this an instrumented stock reference, not untouched stock behavior. DebugToolkit queries demonstrate useful relationships but its commands and hooks can change state. Raw logs stay under work/ with no account/user identifiers in committed conclusions. A full desktop oracle framework would not serve the first experiment and is not added.

## Milestone lookup and current decisions

| Gate | Start here |
| --- | --- |
| L5a/L5 | EditorKit dictionary/cache, R2API AddressReferencedAsset/content provider, ThunderKit catalog import, wiki 1.3.9 guide, SS2VanillaSurvivor + MSU UberSkinDef; then exact local startup/save code |
| L5.5 | DebugToolkit Util, R2Wiki UNet, SS2 state-machine setup, original ModelSkinController/master/body |
| L6/L7 | R2API Prefab/Director/Damage/Items, wiki Stage, SS2 scene content and DebugToolkit Run/SceneCatalog queries |
| L8/L9 | Original SaveSystem/UserProfile/RunReport; source-diff discipline; optional instrumented reference |
| L10/L11 | R2API.Sound, bank lifecycle notes, EditorKit shader helpers and importer graphics settings, with native/source limits |
| L12/L13 | Measured game profiling; original input diffs; importer/provider identity concepts; Burst sources only on a new failure |
| Post-vanilla | [Mod compatibility strategy](mod-compatibility-strategy.md), R2API seams, Starstorm2, BepInEx/NextBep |

No existing laboratory mechanism is removed by this task. What is now unnecessary to invent: a new global GUID lookup system, a new content-pack lifecycle, a generic object-name observer, and a custom asset provider before testing the original providers. Our typed catalog decoder, independent APK/payload receipts, original DLL preservation and Android conversions remain necessary. The changed hypothesis is that L5a should first exercise the game's existing wrapper/manager atop existing providers, rather than starting with a replacement loader. No passed experiment, architecture decision or package pin changed.

## Pinned source entry points

These file links support the source-scoped conclusions above. The structured index contains additional inspected files and version/license/reuse details; activity means last observed commit, not a support guarantee.

| Resource | Inspected entry point | Local use |
| --- | --- | --- |
| R2Wiki | [docs/Mod-Creation/Updating-Your-Mods/1.3.9-Memory-Optimization/Core-API-Changelog-1.3.9.md](https://github.com/risk-of-thunder/R2Wiki/blob/0eefb7ab1c96393cd19e13e140a42c401f5d76e4/docs/Mod-Creation/Updating-Your-Mods/1.3.9-Memory-Optimization/Core-API-Changelog-1.3.9.md) | L5a–L13 |
| RoR2EditorKit | [Editor/RoR2/AddressablePathDictionary/AddressablesPathDictionary.cs](https://github.com/risk-of-thunder/RoR2EditorKit/blob/4128710f74ffbd90bfebc523812e7155fa7bdee3/Editor/RoR2/AddressablePathDictionary/AddressablesPathDictionary.cs) | L5a/L11 |
| RoR2ImportExtensions | [Editor/AssemblyBlacklist.cs](https://github.com/risk-of-thunder/RoR2ImportExtensions/blob/477ad9b52e66e59080049fc3a65645ddb4db2cef/Editor/AssemblyBlacklist.cs) | L5a/L11/L13 |
| ThunderKit | [Editor/Addressable/Config/ImportAddressableCatalog.cs](https://github.com/PassivePicasso/ThunderKit/blob/95a6236df08b0e4bbd5350dd4afdb0927cb7fb6a/Editor/Addressable/Config/ImportAddressableCatalog.cs) | L5a/L13 |
| R2API | [R2API.Addressables/AddressReferencedAssets/AddressReferencedAsset.cs](https://github.com/risk-of-thunder/R2API/blob/f539511eabf87f02afddb5a83cafd2f4704c85ad/R2API.Addressables/AddressReferencedAssets/AddressReferencedAsset.cs) | L5a–L11 |
| RoR2ThunderBurster | [Editor/Core/DependencyInstaller.cs](https://github.com/risk-of-thunder/RoR2ThunderBurster/blob/9cbfd8c807e887111227b98f2803991c653d4717/Editor/Core/DependencyInstaller.cs) | T06 only on new contract/L13 |
| BurstsOfRain | [BurstsOfRain/BurstsOfRainMain.cs](https://github.com/risk-of-thunder/BurstsOfRain/blob/842395b20c3e947479f0aa89ec56e0b13f30ec9b/BurstsOfRain/BurstsOfRainMain.cs) | Future middleware/mods |
| Starstorm2 | [SS2-Project/ProjectSettings/ProjectVersion.txt](https://github.com/TeamMoonstorm/Starstorm2/blob/a9a4baddc5dd4405e893ab5dfc684eb9e27c26f8/SS2-Project/ProjectSettings/ProjectVersion.txt) | L5a/L5.5–L10/post-vanilla |
| DebugToolkit | [Code/Util.cs](https://github.com/harbingerofme/DebugToolkit/blob/d1e2f0aa4b8ac4747547db0fcd87344953432f06/Code/Util.cs) | L5.5–L8/T08 |
| UnityExplorer | [README.md](https://github.com/sinai-dev/UnityExplorer/blob/1e1fb0e27bff9ab0212b4e61ef1ecb38a502b290/README.md) | L5a/T08 |
| BepInEx | [README.md](https://github.com/BepInEx/BepInEx/blob/5b766a3b7f6c164d4798924a93f3acf4db769d06/README.md) | Post-vanilla |
| BepInEx.Android | [README.md](https://github.com/NextBep/BepInEx.Android/blob/33c989e9099b5f36404480aa842d203a04497c0b/README.md) | Post-vanilla |
| BepInEx.Android.Launcher | [README.md](https://github.com/NextBep/BepInEx.Android.Launcher/blob/fd1a4023fa2f899b24cd75e3e944dfba4e9874a9/README.md) | Post-vanilla |
| MoonstormSharedUtils | [LICENSE.md](https://github.com/TeamMoonstorm/MoonstormSharedUtils/blob/fdafff9423ee2efaab44832f95dcd45ae0d4cc39/LICENSE.md) | L5a/post-vanilla |
| RoRSkinBuilder | [Editor/CodeGeneration/PluginCodeTemplate.cs](https://github.com/KingEnderBrine/RoRSkinBuilder/blob/fcfc5dfe520dd1f14e9e8e156984bc37b8947cdc/Editor/CodeGeneration/PluginCodeTemplate.cs) | L5a/L11/post-vanilla |
| ProperSave | [ProperSave/ProperSavePlugin.cs](https://github.com/KingEnderBrine/-RoR2-ProperSave/blob/d20c6c8e593cacce7de94cba7a211b010b15e33b/ProperSave/ProperSavePlugin.cs) | L5a/L9/post-vanilla |
