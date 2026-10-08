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

Local `PlatformSystems.Init` registers Steamworks load/unload callbacks before the EOS selection path; the later load callback constructs the client and performs its checks (J58 correction). it installs SaveSystemSteam, AchievementSystemSteam and SteamworksEntitlementResolver. Flipping the EOS flag is not an offline adapter. Do not classify stock startup's service calls as harmless because a mod runs after them.

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


## J364 — Executed shader-recovery prior art

Read the pinned upstream parser/recovery implementations before adding the fixed read-only action. [Shader recovery ledger](shader-recovery.md) records exact revisions/licenses/dependency compatibility and real same-program outcomes for Unity_Shader_Decompiler, d3dasm, HLSLDecompiler and dxbc-spirv. Existing EditorKit property metadata and pinned AssetRipper shader exporters remain useful contract sources, but dummy exports are not recovered implementations.

Actual native programs outrank tool assumptions: Unity named output misbinds depth/ramp textures, widens vector math, loses comparison-sign semantics and drops material-linked render-state names. d3dasm and HLSLDecompiler agree on the relevant register-level operations; typed IR retains distinctions. Latest cfglib removed APIs required by pinned d3dasm; the measured compatible pin restores the build. No upstream implementation/game-derived shader copied into public source, and no shader/visual capability inferred from compilation or tool marketing. Recover faithful bindings/Standard segmentation before Android integration; legitimate PC draw observation remains the behavioral oracle where possible.


## J365/J366 — Native records and Android resource integration

Consulted the same pinned four recovery implementations and UnityPy ShaderSubProgram parser before writing the segment reader/binder. Native segment indices and parameter records resolve the generic first-segment assumption; exact record-byte equality is checked. The named parser's supported no-fuse option isolates its temporary-fusion crash. Independent Standard HLSL introduces a wrong vector width in dithering; preserve the failed compilation while finishing typed IR on the identical program.

Unity2021.3 bundled UnityShaderVariables/UnityCG declarations provide current matrix/builtin bindings. The generator binds original buffer columns, I/O semantics and resource/sampler slots to these declarations while retaining register-level expressions. Full per-variant builtin layouts come from shipped parameter records, not guessed common metadata. Native source properties/state outrank named-tool defaults. No upstream unlicensed implementation or original recovered math is vendored; generated shader stays under work/. Combined four-exit device evidence is scoped execution only, no PC parity. See shader-recovery.md and journal J365/J366.


J367 checks actual native keyword/property source disagreement and original globalgamemanagers color setting before broad pipeline integration. EditorKit keyword/property metadata and bundled Unity2021.3 Material/PlayerSettings APIs inform the bridge; exact source shader variants/settings outrank numeric inspector state/exporter defaults.38 existing Unity material clones validate original keyword mappings, then the same composed route supplies actual52 bindings. All source/program/capture material remains private; no upstream implementation or original game logic copied to tracked code.


## J368/J369 — Original custom GBuffer and exact-editor lowering

Before extending native bindings, inspect the same pinned four recovery implementations, UnityPy native parameter records and the exact2021.3 bundled UnityShaderVariables/HLSLSupport declarations. EditorKit shader/material property knowledge still informs clone boundaries; shipped GraphicsSettings/program records override importer defaults. The original custom deferred light shader resolves through globalgamemanagers.assets, not the unrelated resource object with the same local ID. Source Standard packing requires that custom light pass; ordinary Unity deferred reflections are explicitly unavailable until their original pass is integrated.

Independent decompilers disagree at actual sample_c_lz support and Standard dithering vector width. Preserve both failures and use only independently compiled shadow output as the scoped fallback. Unity's actual Vulkan cube-shadow convention supplies resource lowering after the original explicit-LOD form fails compilation. A Succeeded build with36 errors is rejected rather than installed. Real device white silhouettes then identify an HDR-tier mismatch; restore measured source FP16 settings and observe actual render targets. No prior-art or original expression is copied into tracked implementation; recovered source/program math stays private. See shader-recovery.md and journal J368/J369; PC draw/semantic/visual parity remains unproven.


J370 consults the same pinned recovery implementations and current native records before extending to clouds/snow/terrain/reflections. Named-tool resource printing/type information and d3dasm native opcodes remain contract clues; the source program/parameter bytes are authoritative. Exact2021.3 UnityShaderVariables declares unity_SpecCube0 and its sampler, so the new wrapper reuses them. Exact-editor ShaderPropertyFlags confirms source property attributes; actual compiler rejects the assumed rawRenderQueue API. Original material queue serialization supplies the measured fallback distinction and its ambiguity check. Native partial-buffer size outranks the larger common table; omitted shared fields never become invented consumed inputs. No original native math or upstream implementation is copied to public files. shader-recovery.md records the same-program evidence and remaining PC oracle/semantic limits.


J371 inspects pinned EditorKit HopooCloudRemapGUI blend/property handling and ImportExtensions ConfigureAddressableGraphics's original deferred/reflection paths before further recovery. Shipped UI common stencil/color-mask fields reveal a named-tool front/back-only state omission; exact source properties and original clip/alpha programs govern the UI wrapper. Grass/cloth use original deferred/shadow pairs. Original late-prong renderer observations identify a missing clone handoff, so the existing owned material path supplies only accepted native Standard to those renderers while retaining their controllers/layers/unknown materials. New math, source assets and upstream code are not tracked; shader-recovery.md records native contracts and unresolved SpeedTree/grab-pass parsing.

J372 consults the same pinned native recovery implementations and exact-editor declarations before handling shared programs/grab passes. Source CalmWater contains vertex, fragment, hull and domain programs; a two-stage reader would silently lose required stages. Original SpeedTree's thirteen shared programs and CalmWater's384 shared programs have equal type/keywords/parameter identities and measured resource layouts across consumers. Distortion's named grab pass has no indexed code. Preserve those contracts and reject disagreements. Same-program water analysis exposes d3dasm's unsupported hull phase and independent HLSLDecompiler's unknown hull target/undeclared domain input; never stage the incomplete output. Recover source foliage/distortion in the integrated world and retain PC draw/semantic/visual limits.


### Native tessellation lowering — J373/J374

Consulted pinned d3dasm `render/interface.rs` and `render/value.rs`: the domain signature declares `patch` while InputControlPoint rendering can emit `vertices`. Its control-point declarations preserve native signature rows, including unused lanes; those remain the binding contract. Pinned dxbc-spirv conversion/lowered IR and original assembly independently retain hull fork/join and domain behavior. Independent HLSLDecompiler rejects the same hull/domain targets, so its emitted text is not accepted source. The authored straight-line lowering reads constants/instructions from private native inputs, rejects unknown opcodes/topology/consumed patch constants and handles destination-mask lane selection; it copies no upstream/game implementation into public source. Exact-editor Tessellation.cginc supplies the edge-length contract comparison, not invented water math.

The current Vulkan device advertises tessellation, but J373 crashes in its native graphics-pipeline compiler. Hardware features and shader import/build success are insufficient. J374 separately selects original-vertex domain evaluation, retaining recovered material expressions and labeling removed subdivision as a geometry approximation. No normal-run or PC equivalence claim follows. [Exact-editor tessellation documentation](https://docs.unity3d.com/2021.3/Documentation/Manual/SL-SurfaceShaderTessellation.html) describes hull/domain stages; it does not establish this device/driver combination.


### Binary draw oracle / current water decision — J376

The same pinned Unity shader extractor, d3dasm, independent HLSLDecompiler and dxbc-spirv remain the recovery authority's interpreters, with actual original programs/parameter records outranking their output. The shipped non-DX11 CalmWater alternative exposes pass-dependent parameter aliases and missing required feature combinations; neither pretty output nor a parser-only fix can supply absent original programs. Keep current recovered expressions and label topology approximation. Exact-byte program grouping can associate native variants; structural similarity alone cannot establish equivalence.

The new read-only draw exporter consults official [RenderDoc v1.35 replay API](https://github.com/baldurk/renderdoc/blob/v1.35/renderdoc/api/replay/renderdoc_replay.h), [pipeline API](https://github.com/baldurk/renderdoc/blob/v1.35/renderdoc/api/replay/pipestate.h), [shader metadata](https://github.com/baldurk/renderdoc/blob/v1.35/renderdoc/api/replay/shader_types.h) and [D3D11 state](https://github.com/baldurk/renderdoc/blob/v1.35/renderdoc/api/replay/d3d11_pipestate.h). SetFrameEvent selects the actual event; ShaderReflection.rawBytes supplies original code; UsedDescriptor retains resource/range/access identity; GetBufferData uses the actual bound range. It cannot infer Unity owners from visual similarity. The pinned UnityExplorer README and Inspectors/ReflectionInspector.cs member/filter/update path inform the separate read-only material/particle-stream snapshot, without installing an instrumentation framework or modifying the original game. Real PC replay remains unavailable/unverified; fixtures are scoped host checks.

### Equipment/proc content and Android settings — J379

Before implementation, inspected pinned R2API.Items/ItemAPI.cs (`f539511e`) and ProperSave/SaveFile.cs alongside the previously recorded local-vs-cloud filesystem policy. Item/equipment catalog registration, original requirements and separate display bindings are concrete boundaries; a local save directory neither establishes platform identity nor unlocks content. The exact accepted EquipmentSlot, Inventory, GlobalEventManager, HealthComponent, LightningOrb, AmmoPickup and native UI fields provide the measured current contracts. Original actions/buffs/procs/cooldowns and source provider identities govern; authored Android code supplies scheduling/input/preferences and scoped cleanup only. No game/community implementation is copied into public Git.

J383/J384 use the accepted Inventory.UpdateEquipmentSetCount and HealthComponent.TakeDamageProcess paths to identify missing comparison/effect context in the composed game. R2API.Items registration-vs-display separation applies: ExtraEquipment remains unavailable loot; Focus Crystal keeps original close-range damage and actual source impact. Native LegacyResourcesAPI resolves the exact effect key; existing owned provider/catalog/material teardown supplies it. No game algorithm, proprietary implementation, unlock or platform success is copied or fabricated.

### Stage population breadth and source equipment tint — J385

Before implementation, inspected pinned R2API.Director README and DirectorAPIinternal.cs (`f539511e`): stage settings, monster/interactable pools and clones are separate seams; source category weights are floats. Its empty-required-expansion and 1.4.0 timing fixes are version clues, not permission to enable unavailable content. Exact original ClassicStageInfo, DirectorCard and five base DCCS files govern this candidate. Supported cards retain original category/card weights, distance, stage restrictions and unlock fields; unsupported cards, DLC/family pools and full SceneDirector startup remain unavailable. Golem/Lemurian/Wisp default renderer, mesh, avatar/controller and state records come from the current legitimate input. The exact EquipmentIcon binding supplies its measured clear/gray/white tint; no guessed shader or new visual style. No proprietary/community implementation copied into public Git.

## J387 — Composed native loot, healing shrine and Android lifecycle

Before implementation, inspected pinned R2API.Items/ItemAPI.cs and R2API.Director README (`f539511e`): item registration/display/requirements and stage pool/cloning seams are distinct. Exact accepted GlobalEventManager, HealthComponent, CharacterBody, MissileUtils, ShrineHealingBehavior and HealingWard govern the current item/projectile/buff/purchase/ward contracts. Four apparent loot candidates have source unlock requirements and remain unavailable; no false profile/unlock or expansion success is supplied. Four eligible original items retain shipped proc/damage/stack/cooldown behavior. Android supplies dependency bindings, source content, owned placement/materials and cleanup. Existing focus/pause observations will test whole-candidate background/foreground behavior before adding new machinery. No proprietary/community implementation is copied into public Git.


### Composed Golem no-audio call — J391

Before changing the passed audio boundary, inspected pinned R2API.Sound/SoundAPI.cs (`f539511e`): bank/runtime lifecycle depends on actual initialized native middleware, not successful managed registration. The current process's ChargeLaser.OnExit stack and exact shipped IL identify one direct UInt32 StopPlayingID outside the existing optional no-audio guards. Extend only that call using the inherited conditional stack-preserving adapter; original state/AI/effect cleanup and every other method body/type contract remain authoritative. No community/game implementation copied and no fabricated engine/service success.


### J392 — Equipment breadth and completed-session resources

Inspect pinned R2API.Items/ItemAPI.cs at f539511e for EquipmentDef registration timing, valid identity/pickup references and unavailable catalog handling; R2API.Addressables AddressReferencedAsset for explicit handle release. Exact current EquipmentSlot, CharacterBody and projectile fields determine the original missile/saw/black-hole/team-war-cry activation and buff dependencies. Four source definitions have no unlock/expansion requirement and remain ordinary native loot. GoldGat/PassiveHealing/ExtraEquipment stay comparison-only. No community or game implementation is copied into public source.

J391 reports progressive same-process memory growth despite completed object/provider cleanup. Authored presentation teardown uses bundle Unload(false), retaining its loaded shaders/ramps while reloading that bundle each session. J392 restores source shader globals/pipeline and destroys owned cameras/materials before releasing that owned bundle with Unload(true); ordinary Unity unused-asset reclamation runs only after verified complete world/network teardown. Boundary resource counts distinguish retained assets from driver warmup; no live cache purge, gameplay rewrite or leak claim. Whole candidate validation remains required.


### J395 — Original DOT content and completed-session managed lifetime

Before implementation, inspected pinned R2API.Dot/DotAPI.cs and Items/ItemAPI.cs (`f539511e`) with the accepted shipped DotController, GlobalEventManager, BurnEffectController and EffectManager contracts. DotAPI separates catalog identity, native stack infliction, damage evaluation and visual ownership. Android binds exact original buffs/providers and invokes the original catalog initializer; no DOT coefficients or gameplay algorithms are reconstructed. Other DOT buff identities are comparison context only and do not grant expansions/unlocks. Native infliction and damage observations distinguish execution from registration. Existing completed-session ownership supplies the point for measuring GC mode/count/used bytes and collecting managed garbage; live caches and gameplay pools remain intact. No proprietary/community implementation is copied into public Git.


### J399–J401 — Native temporary effects, alternate stage and Lesser Wisp audio

Pinned R2API.Addressables AddressReferencedAsset.cs at f539511e distinguishes provider readiness/ownership from native startup's static-field initialization. Exact current CharacterBody legacy BarrierEffect and temporary equipment contracts expose those missing bindings in the composed game. Reuse accepted provider/material/cleanup boundaries, without copying original or community implementation.

Pinned R2API.Director DirectorAPIexternal.cs at f539511e confirms ScorchedAcres maps to wispgraveyard; actual shipped Run selection and source scene/DCCS/graphs govern recovery. Preserve source weighted supported cards and restrictions, rather than forcing a previously accepted destination. Full original SceneDirector/family/expansion population remains unavailable. Pinned R2API.Sound SoundAPI.cs at the same revision confirms that sound-bank/native lifecycle requires a genuinely initialized middleware runtime. Exact Wisp ChargeEmbers.OnExit IL and the actual Android stack justify one conditional optional sound-stop guard; no fake audio, license or service success.


J402 also consults the preserved HLAPI NetworkServer.SpawnObjects implementation: it activates every validated scene identity before spawning. Exact Siren's Call source data marks all three networked kill volumes inactive. The Android scene context retains those identities/components and validates ownership, while omitting activation of an entirely source-disabled group; mixed activation still rejects until its original lifecycle is available. Moon handling and previously active Sky Meadow volumes remain separate existing paths.

The same pinned shader parsers/native parameter reader expose an exported placeholder's missing default subshader tags. Actual explicit material queue 2000 becomes recovered 2450 when the placeholder wrongly reports default 2000. Restore only original binary-backed subshader tags on the owned placeholder; source material bytes and placeholder program body remain unchanged. Existing renderer binding can then distinguish the explicit override naturally. The composed material check compares every explicit serialized queue with the recovered clone. New flow/splat/vertex-color Standard and opaque vertex-alpha variants use the existing shipped-program pipeline; no original expressions are copied to public Git.


J403 distinguishes MapZone identity-component presence from original HLAPI spawn eligibility. Source and compiled Siren's Call data independently retain three disabled components with scene IDs `[3, 0, 0]`. The existing SpawnObjects implementation filters nonempty IDs, so that filter cannot count all preserved components. Validate the actual owned stage components; use the complete native spawnable-set check only for an active group before invoking SpawnObjects. Disabled source volumes remain disabled, with no invented ID or mission startup success. Existing stage evidence records component and empty-ID counts for the composed device assertion.


J404 reuses pinned R2API.Items ItemAPI.cs (`f539511e`) to keep catalog registration separate from native behavior. Exact current HealthComponent exposes fullHealth/fullBarrier, and native AddBarrier clamps earned value to the original limit. The J403 composed run earns two Topaz Brooch stacks and retains positive barrier at teardown, rejecting a utility-only zero-barrier assertion. Integrated validation now checks original limits while utility assertions stay fixed; no grant/decay/health/stat algorithm or proprietary implementation is copied or modified.


J405 consults pinned R2API.ContentManagement/ContentAddition.cs AddEntityState (`f539511e`): concrete EntityState types must register before catalog initialization. Actual Android HurtStateFlyer index/serialization errors and shipped SetStateOnHurt's serialized type/canBeHitStunned gate govern the correction. Add the unchanged original flyer state, validate supported actors' enabled hurt-state references and keep native catalog round trips. BrotherHurt's original StaggerEnter is already in the selected Brother namespace; preserve it rather than substituting generic pain. No community or game implementation is copied to public Git.

### J407 — Native healing-item breadth and completed callback attribution

Inspect pinned R2API.Items/ItemAPI.cs and R2API.Addressables/AddressReferencedAsset.cs (`f539511e`) before extending the accepted content: catalog identity, requirements, display references, behavior and provider lifetime are separate contracts. Exact source WardOnLevel and TPHealingNova are already comparison identities; their definitions have no unlock/expansion requirement, and Plant is also eligible. Add their actual providers, original state configurations and source buff, while keeping every requirement on other definitions. Original WardOnLevelManager handles level/stack/team/radius, DeskPlantController handles its seed/sprout/healing lifecycle, and TeleporterHealNovaController handles charge thresholds/pulse/healing. Android binds the native callback and owns source/presentation cleanup; no game/community algorithm is copied or reconstructed. Original TeleporterHealNovaWindup directly calls EffectManager.SimpleEffect, so its charge effect is an explicit catalog root; existing implicit projectile owners remain unchanged.

The pinned UnityExplorer Inspectors/ReflectionInspector.cs declared/static-member inspection informs a bounded read-only check of already used gameplay callback owners. Compare callback targets and at most two generated closure layers with existing completed probe/report weak targets. Record owner/member paths and read failures, without invoking callbacks, modifying handlers, installing a framework, dumping arbitrary object values or claiming exhaustive heap/root attribution. This observation is justified by J406's confirmed retained completed-session pairs, and is batched with gameplay content rather than made a separate device proof.
