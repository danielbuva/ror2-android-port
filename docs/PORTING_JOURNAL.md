# Porting journal

Dates below are 2026-09-12 PDT (artifact timestamps use UTC on September 13). Tooling checkpoint: `21792fb`; later commits refine evidence retention and handoff. The original installation remained unchanged. Failed evidence is local, not redistributed.

## J01 — Technical inventory and recovery

Hypothesis: this installed Windows build is the expected Mono Unity title and its content/code are inspectable.
Experiment: full SHA-256 inventory, managed metadata scan, PE imports/architecture, UnityPy serialized-content scan, all-assembly ilspycmd export, full AssetRipper reconstruction.
Result: Unity 2021.3.33f1, Steam build 21587608/player 1.4.1; 143 assemblies, 28,648 types, 18 native PE files, 1,472 bundles, 218 banks. 143 decompilations succeed; 19,679 source files. AssetRipper exports 86 scenes and 53 DLLs by default, not full source reconstruction.
Evidence: work/inventory/, work/decompiled/, work/assetripper/53efd194cd207e66/.
Conclusion: enough recovery to run architecture experiments. No original shader source in scanned shader records. Revisit inventories on input/tool changes.

## J02 — Scanner API mismatch

Hypothesis: serialized metadata exposes a public enable_type_tree field.
Experiment: first UnityPy scanner run.
Result: AttributeError across cached entries. No success claimed; scanner corrected to the actual pinned API and schema bumped from 2 to 3.
Evidence: early per-file caches in work/inventory/graphics/, work/graphics-progress.log, final graphics-summary.json.
Conclusion: final 1,478-file scan has zero parse errors. Old failure caches remain distinguishable by schema-derived key. Revisit after UnityPy changes.

## J03 — Decompiler language mismatch and real source blockers

Hypothesis: default decompiler project output can be fed directly to Unity's compiler.
Experiment: full RoR2 decompile then compile with current Roslyn and exact editor C#9 compiler.
Result: default modern source produced 7,841 C#9 syntax errors. Re-exporting as CSharp9_0 reduces both compiler probes to the same 11 unique first-pass accessibility/ambiguity errors (CS0053×4, CS0507×4, CS0122×2, CS0104×1).
Evidence: work/recompile-progress.log preserves initial counts; work/recompile-csharp9.log and work/experiments/recompile/result.json preserve corrected results; work/inventory/decompilation-csharp14.json vs decompilation.json.
Conclusion: pin decompiler language; don't rewrite syntax by hand. Revisit remaining 11 errors only if source fallback is selected; resolving them may expose further errors.

## J04 — Initial reconstructed compile

Hypothesis: the full export opens in the exact editor.
Experiment: import exported project with pinned MCP.
Result: four ambiguous type errors. A bounded local patch qualifies two Wwise Event fields and two forwarded type names; no gameplay logic changed. Subsequent full import takes about 355 seconds and connects via MCP.
Evidence: work/experiments/reconstruction-baseline.json, reconstruction-patches.json; work/reconstruction-editor.log and reconstruction-patched-editor.log. Transformation: patches/reconstruction-ambiguities.py.
Conclusion: default export is usable for further inspection after a small repair. Revisit only if input/match counts change.

## J05 — Original loading scene and Play Mode crash

Hypothesis: imported original loadingbasic can enter Play Mode.
Experiment: guarded MCP scene load/hierarchy, then Play Mode.
Result: original scene loads. Entering Play Mode crashes the ARM64 editor in BurstCompilerService.CompileAsyncDelegateMethod / Unity.Collections direct-call initialization. Native stack includes PlayerLoopController::EnterPlayMode. No game runtime success claimed.
Evidence: work/reconstruction-patched-editor.log (scene load near line 61630; subsequent crash); work/editor/reconstruction-inspect.json. After restart, work/experiments/reconstruction/inspection.json reports 64 GameObjects, zero missing-script components and zero null material slots in loadingbasic.
Conclusion: investigate player-compiled Burst/Collections versus editor package compatibility. Do not repeat unmodified Play Mode. Shader support flags for dummies do not imply correct rendering. Revisit after a bounded package/integration change.

## J06 — Graphics recovery and unchanged bundle rejection

Hypothesis: recovered shaders or untouched Windows bundles could minimize retargeting.
Experiment: inspect all shader programs and exported shader text; load one original Windows shader bundle on both Android APIs.
Result: all 1,425 shader platform arrays are D3D11; all 1,333 exported shader files have dummy exporter markers. Both GLES3 and Vulkan reject the Windows shader sample for incompatible build target. Compute shaders produce import errors in the reconstructed project.
Evidence: shader-manifest.json, reconstruction.json, windows-shader-prototype.json; GLES/Vulkan run Unity logs.
Conclusion: explicit Android content/shader conversion is required. Revisit with an actual translation/replacement shader, not a renamed bundle or dummy HLSL.

## J07 — Harness module and diagnostics failures

Hypothesis: bootstrap package dependencies suffice for a content-aware harness.
Experiment: first harness editor import.
Result: missing AssetBundle Unity module caused compile errors and Safe Mode prompt. Added the module; restarted the isolated editor; MCP/build then passed.
Evidence: work/lab-editor.log, lab-editor-restart.log.

Hypothesis: complete runtime snapshot fits one logcat line.
Experiment: first GLES device smoke.
Result: process and preserved assembly passed, but truncated JSON prevented runtime-path parsing and sync. Collector now retrieves the full snapshot file using its observed path.
Evidence: work/runs/20260913T010737.382003Z-7630bdfebf6b/ (failure), followed by 20260913T011048.134293Z-7630bdfebf6b/ (pass).
Conclusion: keep file-based structured diagnostics. Revisit only if device access/path behavior changes.

## J08 — Hybrid proof and storage lifecycle

Hypothesis: precompiled utility code plus converted content and a small player can run on adopted storage.
Experiment: original SimpleJSON API under IL2CPP; recovered CommandoVultureGrenadeMesh converted through OBJ → exact-editor Android bundle; install, discover paths, hash-sync, run, capture, uninstall.
Result: G2 visible geometry and utility checkpoint on GLES3 and Vulkan. APK about 27 MiB, geometry bundle about 63 KiB, 261 runtime vertices. Private getFilesDir and emulated persistentDataPath use adopted backing. Native custom driver not integrated.
Evidence: work/runs/20260913T011048.134293Z-7630bdfebf6b/, 20260913T011339.682125Z-b2e9fa9f97ac/, final 20260913T012337.819186Z-46130c90d7a1/. Screenshots visually checked. work/experiments/storage-lifecycle/result.json verifies zero unchanged transfer and payload retention after an APK update.
Conclusion: prefer hybrid architecture with explicit limits. This is a static grenade mesh, not a player character, scene or playable RoR2. Revisit scale with synthetic multi-GiB data before whole-game sync.

## J09 — Full exported closure Android build failure

Hypothesis: a minimal empty scene can AOT-build with the reconstructed project's preserved assembly closure.
Experiment: minimum camera scene, Android IL2CPP ARM64, exact SDK/toolchain; no reconstructed APK installed.
Result: build fails after about 296 seconds with three summary errors. Root IL2CPP VTable conflicts identify duplicate override implementations in types mapped by metadata to Rewired_Core.dll and Rewired_Windows.dll. One error's current conversion context mentions RoR2.LightningStrikePattern, but the conflicting type itself belongs to Rewired_Windows; don't misattribute that as a gameplay algorithm error.
Evidence: work/experiments/reconstruction/build.json and first-failure.json; work/reconstruction-editor-20260913T011747.150764Z.log.
Conclusion: wholesale DLL preservation is not currently viable. Test a lawful Android Rewired integration/adapter, preserving action and serialized type contracts. Hybrid remains selective, not wholesale preservation. Revisit after that boundary changes.

## J10 — Reference and workflow audit

Hypothesis: scene loading alone establishes recovered reference integrity.
Experiment: scene probe plus external-GUID scan across Assets YAML.
Result: loadingbasic has zero missing scripts, while the global scan finds 173 unresolved external GUIDs across 43,168 YAML files and 943,831 references. Package GUIDs/local fileID references are outside this scan's resolution scope.
Evidence: work/inventory/serialized-references.json, scene inspection above.
Conclusion: retain explicit reference-repair milestone. Do not equate scene probe success with global serialization integrity.

Workflow correction: one early inspection request overlapped the long reconstructed build and timed out. It was rerun after build completion. Future agents must serialize editor mutations; the standalone build menu reports dispatch, not completion. Editor call evidence now keeps timestamped progress archives so crashes/timeouts retain their last completed operation.

Final validation: six host safety tests pass; doctor/preflight pass; unchanged inventory/decompilation/graphics/build caches reuse results. work/build-cache-final-check.json records a cached=true result for the exact last passing APK. Generated game material remains ignored; commits contain tooling and authored findings only.

Additional diagnostics proof: `work/experiments/diagnostics-toggle/result.json` verifies that changing the subtree configuration without rebuilding reduces the next runtime hierarchy snapshot to the selected recovered geometry object. Public-field collection was enabled; this object's built-in components expose no matching public fields, so an empty field list is expected. The disposable package was removed after the test.

## J11 — Export-modified Rewired metadata, not an unchanged-original closure

Observation: J09's failing override names differed from recovered source metadata. Compare the same four types in original and exported DLLs without executing either assembly.
Result: exported Core/Windows hashes differ from originals. The Core derived type grows from 5 to 6 methods; the Windows derived type from 2 to 3. Each acquires a forwarding getter targeting the same base slot as its surviving virtual method. The original has one implementation. This matches both J09 conflicting method names. The exported DLLs are transformed artifacts, not byte-preserved original assemblies.
Evidence: work/experiments/dependency-boundaries/20260913T021130.995984Z/ (original/export method bodies and override tables, hashes, reports).
Decision: first T05 candidate becomes original DLL preservation with those exact virtual slots rooted and invoked on ARM64. This is a new discriminating experiment, not a repeat of J09. Full Android controller support, native backend availability, serialized maps and full game closure remain unproven. Revisit replacement middleware only after testing this boundary.

T02 also selects original RoR2.Trajectory and ProcChainMask/ProcType method IL for a bounded ballistic/combat-mask probe with numerical/bit-state assertions. This does not exercise EntityStates, character simulation, platform initialization or full RoR2 closure. Do not promote a future slice pass to full game compatibility.

## J12 — Original Rewired virtual slots pass Android IL2CPP

Hypothesis: bypass the export's added forwarding getters by preserving original DLL bytes, not by patching input behavior.
Experiment: original Rewired_Core and Rewired_Windows in the existing lab; explicit linker roots for both failing base/derived pairs; allocate uninitialized instances, suppress finalizers, invoke the original base virtual method. Core returns expected 1; Windows returns the assigned expected 37. Constructors/native input backends are deliberately not initialized.
Result: forced ARM64 IL2CPP Vulkan build succeeds in 67 seconds; both actual slots execute correctly on the authorized device, with PID/attempt-correlated JSON, G2 screenshot, adopted placement and cleanup. Original DLL hashes recorded. No middleware code, original assets or evidence committed.
Evidence: work/experiments/rewired-original/20260913T021247.788313Z; APK SHA-256 19dab055b304e08fc5429d40e77e105d6b64aef5b20627b796be7239810aeb43.
Decision: T05's recorded AOT conflict is resolved for this bounded probe. Preserve originals as the next closure candidate. Full closure, ReInput initialization, serialized mapping and Android controller operation remain open; do not label Rewired fully compatible. The original exporter failure is retained, not overwritten.

## J13 — Package resolution precedes Collections probe compilation

Observation/hypothesis: pinned Collections 1.2.4/Burst 1.8.11 (versions bundled with exact editor) should permit a representative native list/job probe.
Result: first attempt failed before player compilation, CS0246 BurstCompileAttribute. The live package lock still lacked the requested packages after MCP refresh; this is package-resolution sequencing, not a runtime compatibility result. No APK installed.
Evidence: work/experiments/collections-runtime/20260913T021631.935352Z, including full editor log, stage, build failure and first-failure.json.
Next/revisit: restart only the isolated lab editor after the terminal failed build, allow manifest resolution before staging/compiling the probe, then retry. No version change or cache clearing is justified by this failure.

## J14 — Pinned Collections/Burst candidate executes in editor and on ARM64

Hypothesis: package-built artifacts from a justified exact-editor-era package set avoid the recovered player direct-call setup for representative operations.
Experiment: Collections 1.2.4, Burst 1.8.11 (both versions bundled with the exact editor), Mathematics 1.2.1; NativeList add/swap-remove, NativeArray/NativeSlice, scheduled sum job and disposal. A BurstDiscard sentinel distinguishes compiled execution from managed fallback. Packages resolved after J13's isolated restart.
Result: editor and Android both return sum 31 and post-removal sum 24; Burst execution sentinel true in both. Android PID/attempt correlated; build terminal before editor Play; device installed on adopted storage and cleaned up. This validates a package candidate, not every game-consumed API/layout or full reconstructed Play Mode.
Evidence: work/experiments/collections-runtime/20260913T021910.087323Z/editor-probe.json and android-probe.json, APK/build/capture receipts.
Next: T07 selected original game IL; later test full original managed closure with these package candidates. No arbitrary version sweep or broad cache clear.

## J15 — Slice metadata reader failure, before Unity build

Hypothesis: retain compiler/runtime attributes while pruning only the selected mathematical types and full-game discovery registration.
Result: legacy Cecil attempted GAC resolution while decoding a compiler attribute enum under modern .NET; the preparation subprocess failed before Unity build dispatch. The first stage/console are preserved under work/experiments/ror2-slice. No game method rewrite or device install occurred.
Repair: preserve primitive/enum attribute blobs without unnecessary value decoding, inspect their constructor references, and use source-directory dependency resolution. Compiler/runtime attributes remain; only the full-game HG discovery opt-in is omitted from the isolated slice. Four authored-fixture tests cover retained IL/source identity, missing types, dangling dependencies and output outside ignored work. All ten host tests now pass.
Revisit only if a new attribute form requires supported closure inspection. This is a metadata-tool failure, not a game/AOT compatibility finding.

## J16 — Original RoR2 trajectory/proc-mask IL executes on ARM64

Experiment: retain three self-contained original RoR2 types (35 method bodies), preserve assembly/type identities and verify normalized method IL/locals/handler fingerprints after writing. Remove other types/resources and full-game HG discovery opt-in; retain compiler/runtime attributes. This is a type-pruned original-code assembly, not an unchanged full DLL and not C# source reconstruction.
Result: ten authored assertions pass on each of three fresh Android PIDs, each alive over 36 seconds. Ballistic apex/duration/position and solve-integrate consistency; proc bits/idempotence/removal/value-copy behavior. ARM64 IL2CPP Vulkan; adopted package/payload; visual capture checked; owned package removed.
Evidence: work/experiments/ror2-slice/20260913T022358.230312Z, slice-provenance.json and launch-1..3/probe.json; local LAST_KNOWN_GOOD_MANAGED_SLICE receipt. Ten host safety/transform tests pass.
Decision: T07 bounded original-code execution passes. Full closure/EntityStates, original startup, character and stage remain unproven. Next discriminate full original-assembly AOT with the passing package candidates, without export-added forwarding getters. This is a new assembly-input hypothesis, not a repeat of J09's exported closure.

## J17 — Original closure provenance excludes an export-only dependency

Observation: full original-set staging found System.Runtime.CompilerServices.Unsafe.dll only in exported Plugins, not in the legitimate installed Managed directory. Original managed inventory has zero assembly references to that name.
Result: staging stopped; no build dispatched. Partial staging and first-failure evidence retained under work/experiments/original-closure/20260913T022959.574125Z.
Decision: omit an export-only assembly only when no original assembly references it. The next attempt stages 45 original DLLs; package/current-lab providers supply Burst/Collections/Mathematics/UI/SimpleJSON. Full RoR2 is rooted, with no game startup/auth changes. This compares original inputs, not another export rewrite.

## J18 — Full original RoR2 assembly AOT and harness smoke pass

Experiment: 45 unchanged original DLLs, full RoR2 assembly explicitly preserved, pinned package providers from J14, existing Vulkan lab scene. No game startup, authentication or native-service adapter.
Result: terminal ARM64 IL2CPP build succeeds in 204.7 seconds, zero build errors. All 45 staged DLL hashes verified after build. Existing utility/geometry smoke passes on the authorized device, package and payload on adopted backing, screenshot visually reviewed, owned package removed. Only captured error is the intentionally tested incompatible Windows shader bundle.
Evidence: work/experiments/original-closure/20260913T023057.067759Z; work/runs/20260913T023811.889560Z-68c7c68a5f74. APK SHA-256 68c7c68a5f743bf22ecc0bfe98e7839ddb935ecbcdf8d107529b50e34171040e.
Decision: original input metadata removes the exported closure's AOT blocker without recreating Rewired. The full game assembly can coexist in the harness; this does not prove game startup or all native/API contracts. Next repeat the measured game-method assertions against the full assembly before recovered scene work. Preserve the staged closure and package lock; do not stage a second RoR2.dll alongside it.

## J19 — Full namespace exposes an authored probe ambiguity

First T07c build fails CS0104: Path resolves to both RoR2.Path and System.IO.Path. The pruned slice had hidden the former. No device installation occurred. Full failed stage and terminal build/console preserved at work/experiments/original-closure-runtime/20260913T024020.230186Z. Qualify the authored file path with System.IO; no original code changes.

## J20 — Full unchanged RoR2 DLL passes original method assertions

Retry after J19 changes only the authored System.IO.Path reference. All 45 staged DLL hashes match original inputs after build. Ten trajectory/proc assertions pass on three distinct cold Android processes; measured survival 36.83, 36.91 and 36.89 seconds. Only captured errors are the known Windows-target shader rejection. Screenshot reviewed; adopted placement/data backing retained; owned package removed.
Evidence: work/experiments/original-closure-runtime/20260913T024051.910924Z; APK SHA-256 b55aaed78502246f19d6125b3d0f6a832f2cb6cc3510580dbb51604a13a27e73. The historical JSON field sliceHash equals the full original input hash in this attempt; provenance explicitly records fullOriginal=true. Stage and package graph archived.
Decision: L3 meaningful managed execution passes with the full original assembly, without reconstructing game code or changing authentication. This does not exercise all methods, native middleware, original startup, EntityStates or character simulation. Replan advances to L4a required scene/prefab reference audit.

## J21 — Scoped scene/prefab reference audit and original script identities

Observation: global GUID counts cannot establish local file IDs or imported subasset/script identity. Hypothesis: loadingbasic provides a small discriminating content closure, while the Commando body gives a dependency-rich comparison.
Experiment: read-only YAML traversal, followed by explicit imported-ID queries through pinned Unity MCP without Play Mode or prefab instantiation. loadingbasic closure contains 122 files / 10,580,073 bytes; CommandoBody reaches 2,864 files / 179,659,008 bytes. No duplicate asset GUIDs found.
Result: all 1,169 imported IDs queried in the reconstructed project resolve, all MonoScript classes resolve. The flagged scene fileID 102900000 is a valid SceneAsset, not a YAML object defect. All 161 queried DLL script IDs resolve to the same types with original DLLs in the lab; all 45 original hashes remain unchanged after import. This does not prove serialized field compatibility or prefab execution. Two missing GUID references belong to one dynamic TMP fallback atlas; source font is present, runtime regeneration is untested.
Evidence: work/experiments/scene-closure/20260913T024833.204285Z; static closures, exported/original editor identities, source stage and query configurations, assessment. No device build/install this experiment. Ten host tests pass.
Failed orchestration: the first lab query was sent before its refresh completed and the menu was unavailable. Preserve console in this attempt; wait for the terminal refresh before retrying. Retry then passed. This was an orchestration error, not a content finding.
Decision: L4a audit complete; L4 device gate stays open. Next stage only loadingbasic, map measured package UI identities, preserve original DLL references, then build/load an Android scene bundle. Commando’s static closure reaches skins/effects and is not a minimal simulation payload. Runtime catalog reachability, rig/animation behavior and material readability remain separate assertions.

## J22 — Loading scene staging and missing payload prerequisite

Staged only the measured loadingbasic closure plus 45 hash-verified original DLL providers; retained exported GUID metadata. Four package UI MonoScripts resolve correctly, enabling 32 exact serialized reference remaps. Two recovered Assembly-CSharp scripts are copied unchanged as source; this is not an all-original-DLL-only content build. Application GameObject 37 is set inactive in the derived scene to prevent RoR2Application.Awake and the entire startup/authentication chain from executing. No original DLL or entitlement behavior is patched.
First forced APK build succeeded but its receipt lacked loadingbasic-lab. The scene runner refused installation. Evidence: scene-runtime/20260913T025548.223810Z/bundle-attempt-1. Initial code issued separate scene and geometry bundle builds to the same output directory; changed to one explicit combined build list to remove that ordering ambiguity. The retry produces both payloads. The missing payload is established; deletion by the second invocation was the working hypothesis, not separately traced.

## J23 — Isolated recovered loading scene executes on Android

Combined bundle build and ARM64 IL2CPP APK pass. Device PID 3860 loads loadingbasic from a separately synced ~1 MiB Android bundle. Report: 26 objects remain in the loaded scene, zero missing script components among those objects, one active camera; original application object inactive and RoR2Application.instance null. Measured 35.78-second survival. Screenshot shows the original loading sprite on its black background; no new captured exceptions beyond known Windows shader rejection. Package and data backing verified on adopted storage; owned package removed.
Evidence: work/experiments/scene-runtime/20260913T025548.223810Z contains build/input/UI mapping/scene isolation receipts, failed first payload attempt, archived stage/package graph, runtime JSON, logs and visually checked screenshot. Ten host tests pass.
Limits: this is a scene deserialization/content proof, not game startup, full L4, animation validation or gameplay. Components moved to DontDestroyOnLoad are outside the current scene-local missing-script count; address that precise observation gap before full scene acceptance. Dynamic fallback font rendering/regeneration is not exercised. No dependency-rich prefab has instantiated.
Next: L4c persistent-object/component audit and bounded dependency-rich prefab content probe; retain inactive application startup. Preserve full L3 rollback and this bounded scene receipt without declaring the complete milestone passed.

## J24 — Persistent scene objects and temporal loading sprite pass

The prior scene-local count omitted objects moved to DontDestroyOnLoad. Compare scene-valid runtime object IDs before/after load, then inspect newly created persistent objects without Play Mode on the host. Device report finds 26 scene-local and 38 persistent Canvas objects, zero missing scripts across both. Eight sprite changes observed over two seconds; screenshot reviewed. Zero active TMP text objects means font rendering/regeneration is still unexercised.
Evidence: work/experiments/scene-runtime/20260913T030620.915557Z. No new captured exceptions; application startup inactive; owned package removed. This closes the specific observation gap, not startup or font acceptance.

## J25 — Commando static closure omits deliberately deferred skin content

Before building the prefab, inspection found empty Animator avatar/controller, SkinnedMeshRenderer mesh/materials and default skin parameters. These are intentional runtime AssetReference fields, not missing YAML PPtrs. Original ModelSkinController/SkinDef code loads them through Addressables. The static-closure-only hypothesis is insufficient; no knowingly empty prefab device build was attempted.
Decode the original catalog using original ContentCatalogData.CreateLocator in an editor-only tool, without provider initialization or asset/service loading. Typed locations identify animCommando.controller, the mdlCommandoDualies FBX subobjects, skinCommandoDefault_params and matCommandoDualies. Catalog bundle dependency lists have 1,009–1,035 entries. Do not blindly copy or retarget that whole list. Exported subassets and their type/IDs are verified independently.
Evidence: work/experiments/scene-runtime/20260913T030959.488736Z, boundary-observation.json, default-skin-addresses.json, default-material-address.json, catalog queries and default-asset-identities.json. Revisit full asset-loader semantics with a bounded local provider/catalog experiment after content proof.

## J26 — Inactive original Commando prefab integrity passes on ARM64

Hypothesis: six measured default assets can establish recovered component/rig integrity while original startup and character simulation stay inactive. Stage the measured prefab closure, add 42 missing static dependencies of the resolved controller/avatar/body mesh/two gun meshes/material, and set only the derived prefab root inactive before instantiation. Bind those assets explicitly on the diagnostic clone; original DLLs unchanged. This bypasses no ownership/authentication check and does not claim original skin-loader execution.
Build passes in 195.86 seconds. Separate prefab bundle is 56,850,256 bytes. Device PID 6748: 133 objects, original CharacterBody and model linkage, zero missing scripts, body mesh 5,422 vertices, 78 bones and 78 bind poses, no missing bone/material references, two complete gun MeshFilters, valid avatar, one animator/controller with 35 clips. Root remains inactive. Scene/persistent checks and eight sprite changes also pass. Survival 35.98 seconds, no new captured exceptions, adopted backing verified, owned package removed.
Evidence: work/experiments/scene-runtime/20260913T030959.488736Z; APK SHA-256 78031249d21fd46c68f577d087e2556c3b5dbcc8de4ce03a05bac189744a2844. Stage, typed catalog mappings, package graph, build/payload receipts and device capture preserved. Ten host tests pass.
Limits/next: screenshot shows loading sprite, not the intentionally inactive character. Original skin loader, visible posed/animated Commando, font rendering, original startup, authority and character simulation remain unproven. L4d should introduce visible character content as the next variable; do not promote this to full L4 or L5.5.


## J27 — Visible pose succeeds but required Android captures fail

Attempt work/experiments/scene-runtime/20260913T033139.755423Z visibly renders Commando and measures 14 changing bones. However, Unity's Android screenshot API prepends persistentDataPath to the supplied absolute filename, creating a duplicated path. Both required screenshots fail to save. ADB capture is preserved but does not satisfy paired-pose acceptance. The host exception handler incorrectly retained success=true after the transfer failed; preserve runtime-result-as-emitted.json and correct the terminal assessment to failure. Fix the handler to clear success on exceptions and test this precise failure with a passing runtime marker. Retry changes only screenshot filename handling and truthful receipt aggregation; original content/assemblies unchanged.

## J28 — Original Commando visible animation content passes on Android

Hypothesis: recovered skeleton/mesh/clip data can animate correctly without activating original gameplay behaviours. Copy only original transforms and renderers into a diagnostic preview; retain original avatar and sample RunForward through a manual playable graph with events/root motion disabled. Use the original texture with an authored diagnostic shader. Original Commando prefab and RoR2Application remain inactive; no state machine, authority, original skin loader or platform service is claimed.
Result: retry work/experiments/scene-runtime/20260913T033741.737311Z passes. PID 9011 survives 35.93 seconds. Both paired PNGs are pulled and visually reviewed: recognizable Commando with distinct leg/arm poses. Sample times 0 and 0.35 seconds of the one-second clip change 14 of 78 bones, maximum 78.99 degrees. Preview has zero gameplay MonoBehaviours. All 45 original DLL hashes verified after build. No new captured exceptions beyond the known Windows shader rejection. Adopted placement/data backing verified; owned package removed. APK SHA-256 028b4982fe14878a9662ee4b419b9da1f7efa1cda5c1ba6d22f59448c718b25f. Stage, package graph, payload/build identities and failed attempt preserved. Eleven host tests pass, including failed required-capture aggregation.
Decision/replan: L4 isolated content gate passes across J21–J28. Diagnostic asset binding/materials are accepted for this content gate; original skin loading and font rendering remain unproven. Retain Architecture C and proceed to L5a original asset-loading/startup/profile audit, selecting one measured provider assertion before application activation. L5.5 simulation remains wholly open. No simulation/playable/run checkpoint advances; retain L3 runtime and update only content checkpoint.


## J29 — Community prior art sharpens L5a without repeating device proofs

Research-only checkpoint at expected HEAD 3cfc3a4. Sixteen public repositories inspected at recorded SHAs under ignored work/reference-repos; source index and authored conclusions committed, no third-party/game source copied. R2Wiki's memory-update guide matches the pinned game's deferred SkinDefParams and AssetOrDirectReference/AssetAsyncReferenceManager mechanisms. EditorKit's bundled mapping/cache and subasset heuristics require current-input checks; ThunderKit copies catalogs rather than retargeting bundles. R2API's compatibility onLoad event is not an all-assets-ready guarantee. Starstorm2 optional executor flags were checked directly, including disabled publicizer/MMHook/Wwise blacklist. ProperSave demonstrates physical/cloud filesystem separation, not vanilla-profile portability.

Decision: recommend a tiny local Addressables initialization/catalog recipe using existing bundle providers for the original controller wrapper's LoadAsync/Reset lifecycle before writing a custom provider. Explicit original cleanup ticking is needed in this isolated probe because RoR2Application.onUpdate stays inactive. Platform and profile startup remain unexecuted; detailed ranked candidates and pass/failure conditions in community-prior-art.md. L3/L4, Rewired original-slot attribution, Burst1.8.11/Collections1.2.4/Mathematics1.2.1 and Architecture C unchanged. No new APK, game launch, profile access or capability pass.

Health: initial doctor failed only because the local pinned MCP server was stopped (work/research-bootstrap-doctor.log). Restarted existing scripts/mcp-server.sh; after editor registration, doctor passes (work/research-doctor-final.log). Preflight and eleven safe host tests pass. Archived L4 45 DLL hashes and accepted APK hash rechecked; J14 editor/Android reports and L3 receipts read as historical evidence. No passed runtime experiment repeated. Next: resume the exact L5a first-provider assertion after this documentation task.

## J30 — Original Addressables initialization exposes a stripped reflected constructor

L5a-1 first attempt work/experiments/scene-runtime/20260913T043940.529584Z uses a valid local bootstrap catalog and existing providers; no original application/body is activated. Before installation, a successful build was superseded after source review identified initialization handle autorelease; its receipt/source is preserved in preinstall-handle-review. The device build explicitly retains and balances that handle.
Device PID 13381 stops the probe in phase initialize with MissingMethodException for ProviderOperation<ResourceManagerRuntimeData>'s default constructor. The controller request is never reached; this is not a provider/content/entitlement failure. The stripped ResourceManager IL lacks ProviderOperation's constructor. Source inspection shows ResourceManager/LRUCacheAllocationStrategy creates the closed operation through reflection. Stage/build/catalog/settings/logs and owned cleanup are preserved. Next candidate retains precisely ProviderOperation`1 through link.xml, leaving all original DLLs unchanged. Unity's stripping guidance identifies explicit preservation as the mechanism for reflection/content roots; community catalog import does not generate an Android player preservation recipe for this laboratory. Do not replace the providers or packages for this failure.

## J31 — Preservation descriptor was not discovered

Retry work/experiments/scene-runtime/20260913T044529.266961Z repeats J30's missing constructor on PID 14458. The authored XML was staged as ControllerAddressLink.xml; Unity requires a descriptor named link.xml. Therefore this run does not test the preservation hypothesis. Preserve the failed stage and receipt; move the descriptor destination to ControllerPreservation/link.xml in the next attempt. Verify the stripped assembly contains the constructor before installation. Providers, packages and original binaries remain unchanged. Both failed attempts removed the owned device package.

## J32 — Reflection preservation must cover the measured operation factory

Attempt work/experiments/scene-runtime/20260913T044754.165930Z verifies ProviderOperation's constructor survives the corrected link.xml. Device PID 15411 progresses to initialization objects, then fails on GroupOperation's default constructor. Owned cleanup passes. The original providers remain untested, not disproven. Reassess the incomplete-root hypothesis after these two distinct reflected-allocation failures: ResourceManager.CreateOperation also dynamically constructs groups, typed chains and completed operations used by this probe's initialization, loading and negative controls. Preserve these four measured types together. InstanceOperation belongs to untested object instantiation and is excluded; typeless chains use direct construction. Keep packages/providers and all original DLLs unchanged. Preserve the failed stage, build, stripped IL and report before a fresh attempt.

## J33 — Original controller deferred loading passes on Android

Measured factory preservation retains ProviderOperation, GroupOperation, typed ChainOperation and nested CompletedOperation; stripped IL confirms their constructors before installation. No input DLL changes and no custom provider. The original Addressables initializer consumes a valid owned bootstrap settings/catalog, then original bundle providers serve one typed local controller location.

Device evidence: work/experiments/scene-runtime/20260913T045406.130233Z. PID 17377 survives 50.17 seconds. Original AssetOrDirectReference/AssetAsyncReferenceManager returns the controller with 35 clips including RunForward, shares handles between two owners, retains the second owner after the first reset, releases the handle and bundle after final reset and original cleanup ticks, then reloads successfully. Three completion callbacks occur. Missing-key and wrong-type requests fail with the expected InvalidKeyExceptions. Original application and both filesystem roots remain null. Only those two intentional failures and known Windows shader rejection appear in captured exceptions; crash-buffer entries concern historical other-package processes. Screenshot reviewed: expected lab geometry, not a rendered character acceptance claim. Adopted package/data backing verified and owned package removed.

APK SHA-256 3298285cbfd59165276a8fe74fb305e882e8f30bf69b365cc6aa98cd64dafc86. All 45 original DLL hashes unchanged, exact package graph/build/payload/settings/catalog and stage archived. Eleven host safety tests pass. L5a-1 passes; L5 and L5.5 remain open. Explicit calls to original manager Update are diagnostic scheduling, not game-loop integration. Retain Architecture C and existing providers. Next: avatar subobject identity through this accepted loading path, then SkinDefParams/BakeAsync separately; do not activate the original body/application yet. Failed attempts J30–J32 remain preserved; L3/L4 checkpoints unchanged.

## J34 — Original avatar subobject request passes on Android

Observation: the original prefab stores avatar GUID and subobject name separately. Original AssetReference.RuntimeKey composes GUID[name], as also handled by the pinned EditorKit BaseGameAssetReferenceTDrawer. The original catalog's Avatar location points into mdlCommandoDualies.fbx, while J26's imported identity identifies a standalone exported mdlCommandoDualiesAvatar.asset (file ID 9000000). Hypothesis: map the exact original typed runtime key to this verified recovered asset through existing providers, without inventing an FBX path or replacing the original wrapper/manager.

Attempt work/experiments/scene-runtime/20260913T053223.468179Z passes on Vulkan ARM64. PID 19424 survives 51.13 seconds. The original typed request returns mdlCommandoDualiesAvatar, Unity isValid=true and isHuman=false. The exact compound key and actual bundle asset name match. Shared ownership, retention after one reset, delayed final release/unload, reload and three callbacks pass. Missing subobject and wrong type fail explicitly. Original startup/filesystems stay inactive. Only the two intentional invalid-key errors and known Windows shader rejection are captured; no current-PID crash entries. Screenshot reviewed: expected lab geometry, no new character-rendering proof. Adopted placement/backing and owned cleanup pass.

All 45 original DLL hashes unchanged; APK SHA-256 abd2294b29f6b0db963ab317db29cb1239fa169eae6d884e7883a323e58f9655. Full stage, typed identity mapping, package graph, APK/payload receipts and device evidence archived. Fifteen host tests pass. L5a-2 passes; retain existing providers and Architecture C. Cleanup scheduling remains diagnostic. L5/L5.5 stay open. Next: separately measure SkinDefParams and original SkinDef.BakeAsync template generation; body/application activation remains deferred.

## J35 — Skin probe diagnostic root label is invalid for the original wrapper

Attempt work/experiments/scene-runtime/20260913T054513.346891Z initializes successfully, then fails before BakeAsync with an invalid operation handle. The diagnostic root label lab-default-skin is accepted by an Addressables locator but original AssetReference.RuntimeKeyIsValid requires a GUID (optionally followed by a subobject). The original manager returns a default handle for an invalid reference; the wrapper then reads its Result. This is a probe-root error, not evidence against parameter loading or baking. Device survives 71 seconds; owned cleanup passes. Preserve stage/build/report before retry. Use the measured exported SkinDef GUID for the diagnostic root request, explicitly distinguish it from the unchanged original deferred parameter address, and assert RuntimeKeyIsValid before load. No provider, content or original game code change is needed.

## J36 — Original default skin baking passes on Android

The corrected diagnostic root uses the measured exported SkinDef GUID, not a fabricated original catalog identity. Its deferred SkinDefParams address remains the original game value. Before building, independent traversal of serialized prefab transforms predicts three renderer paths and three mesh-replacement paths/keys, one shared material address, and zero activation/light/projectile/minion templates. Only the parameter asset is newly copied; existing root/reference content and all 45 original DLLs remain intact. Prior art: RoRSkinBuilder's current generated skin structure separates SkinDefParams; current original BakeAsync determines the actual deferred-load and release contract.

Attempt work/experiments/scene-runtime/20260913T055011.793475Z passes on Vulkan ARM64, PID 21690, 70.92 seconds. Original BakeAsync produces exactly the expected three renderer and three mesh templates with matching paths/material/mesh keys and no extra templates. A repeated bake returns the same runtime skin. The original manager's parameter handle becomes invalid after releasing the probe's witness owner and ticking original cleanup, demonstrating that BakeAsync balanced its acquisition. Shared SkinDef ownership, final bundle release, reload and intentional missing-key/wrong-type failures also pass. Original application and filesystem roots remain inactive. No unexplained captured exceptions or current-PID crash entries; expected Windows shader rejection and negative controls only. Screenshot reviewed: lab geometry, not skin application. Adopted backing verified and owned package removed.

APK SHA-256 7a9f93c6871f9e9baf65ededdfd30c694d96d63de2465caacdcc3ac75f17c7d6. Stage, independent contract, package graph, input/build/payload receipts and device evidence archived. Fifteen host tests pass; public staged-content privacy gate required before commit. L5a-3 passes; L5/L5.5 remain open. Next: original RuntimeSkin.ApplyAsync on the inactive model after measuring material and mesh request mappings. Diagnostic cleanup scheduling and absence of full startup remain explicit limits. J35 is retained as a failed probe setup, without advancing any passing checkpoint.

## J37 — Skin application probe used the wrong generic list type

Attempt work/experiments/scene-runtime/20260913T061436.621675Z fails player compilation in 2.67 seconds. The pinned assembly's RuntimeSkin.ApplyAsync fourth argument requires List<AssetReferenceT<GameObject>>, while the authored probe supplied List<AssetReferenceGameObject>. Generic lists are invariant. This is a harness API mismatch; no new APK was accepted and no device run occurred. Preserve the failed build receipt and source stage. Correct only the probe's empty ownership-list type and prepare a fresh attempt; game DLLs/content/provider behavior are unchanged. The actual compiler signature takes precedence over recovered-source spelling.

## J38 — Original skin application fills inactive model mesh components and material records

Current original RuntimeSkin.ApplyAsync directly assigns mesh components but writes materials to CharacterModel.baseRendererInfos; the later model update is responsible for renderer material slots. Community skin guidance and R2API's renderer-info usage agree on the record contract. Map the measured material GUID and three mesh subobject keys to already recovered assets. Instantiate the original model beneath an inactive parent, assert all three mesh slots start empty, then call the original method. Keep application/body lifecycle inactive. Cleanup follows the original ModelSkinController returned-ownership-list pattern through original managers with diagnostic cleanup ticks.

Attempt work/experiments/scene-runtime/20260913T061649.849553Z passes, Vulkan ARM64 PID 23379, 70.87 seconds. Original method assigns CommandoMesh (5,422 vertices), GunMesh.001 (601) and GunMesh (601) to the expected components. Three CharacterModel renderer records reference the correct recovered material and renderer identities; zero renderer material slots populate while the lifecycle is inactive, an explicit unproven rendering step. Model remains inactive; all acquired material/mesh handles release, and skin/bundle release/reload checks pass. Only known shader-target rejection and intentional missing-key/wrong-type errors are captured; no current-PID crash entries. Expected lab screenshot reviewed; no rendered-skin claim. Adopted backing and owned cleanup pass.

All 45 original DLL hashes unchanged. APK SHA-256 f79aea11d7fd50f98cccb7a405fece0e774dc94182f74d2b130570a9a5abc6a4. Stage, measured application contract, build/payload/package receipts and device evidence archived. Fifteen host tests pass. J37 preserves the compiler-only failed setup. L5a-4 passes within the stated method contract, not full live model rendering, startup or simulation.

Decision: stop expanding isolated asset probes and proceed to L5b startup/profile integration. Existing static trace shows InitializeGameRoutine invokes Wwise initialization before Addressables, roots its filesystem at Application.dataPath, then enters PlatformSystems and Steam client initialization. Revalidate the pinned signatures and select the first bounded lawful startup segment; establish Android-only profile/content roots before enabling saves. Do not blindly activate the whole routine, manufacture service success, or skip mandatory checks. L5 startup/menu remains required before L5.5 original character simulation.

## J39 — First original startup phase and independent profile filesystem pass

Revalidated the pinned DLL metadata and existing startup/profile prior art. Select only InitializeGameRoutine's first MoveNext (priority, searchable-attribute scan, loading flag) and its nested PreFrame phase on an inactive original application component. Require the discovered phase targets to equal FlashWindow.Init before execution; never resume the outer routine afterward. Independently test the original Zio filesystem implementation beneath a fresh Android-owned directory and a read-only payload view. No original application Awake, global filesystem assignment, Steam saves, audio or platform initialization is performed.

Attempt work/experiments/scene-runtime/20260913T063714.317149Z passes on Vulkan ARM64, PID 24964, 50.24 seconds. Original first yield and PreFrame complete. Sentinel write/read, reopening the filesystem in the same process, root separation, path traversal boundary, read-only content denial, sentinel deletion and untouched original filesystem globals all pass. This is a filesystem candidate, not original UserProfile serialization or a cold-launch save test. Adopted placement/backing and owned package cleanup pass. Only the known Windows shader rejection is captured; zero current-PID crash entries. The reviewed screenshot shows the expected lab mesh, not the original startup screen.

The prediction that FlashWindow's kernel32 static initialization would fail during Init was disproved for this path. Preserved generated C++ shows Init registers callbacks without calling the FlashWindow type initializer. Later notification callbacks/native calls remain unproven. Do not add an adapter for an unobserved failure. SearchableAttribute's current Initialize uses ScanAllAssemblies; the cached-name-file code is not this path's requirement.

All 45 original DLL hashes remain unchanged. APK SHA-256 d28e2287801d7ac96d0cf5831f6c8f5fb3d8b9a450e05ef0ecbc9c20f1e49997. Stage, metadata, generated Init excerpt, build/payload/package receipts and device evidence archived; LAST_KNOWN_GOOD_STARTUP_SEGMENT records this bounded pass. Fifteen host tests pass. L5b-1 passes; L5 menu, L9 actual profiles and L5.5 simulation remain open. Next isolate the recovered loadingbasic scene handoff and loading UI references, stopping before EnableBehaviours and Wwise.

## J40 — Original startup recognizes recovered loading scene; retained in-place update

After J39 PreFrame, load the accepted recovered loadingbasic bundle additively, select its actual scene, and assert the original persistent LoadingScreenCanvas and percentage references. Inspect the recovered inactive application's six enable-list references. Advance the original routine exactly twice through its pinned loading-UI frame yields and stop before EnableBehaviours/Wwise. The routine still uses an inactive diagnostic application host; do not claim the recovered application lifecycle or resume its empty enable list as proof of component startup.

Attempt work/experiments/scene-runtime/20260913T070000.602652Z passes on Vulkan ARM64, PID 28332, 50.67 seconds. Original routine recognizes loadingbasic; original Canvas/percentage references exist and two frame yields complete. Recovered application remains inactive. The six disabled/inactive targets are GlobalShaderTextures, two PostProcessVolume components, InterpolationController, NGSS_Local and FPSQueue. No targets were enabled. Reviewed capture shows the recovered black loading screen with 0 percent and the loading sprite: this deliberate stop is not a hang or menu acceptance. Profile sentinel assertions pass; unique per-launch directories permit repeated manual launches without reusing a prior sentinel directory. Actual profiles remain unintegrated.

User requested a manually launchable retained app and in-place updates. Reinstalled accepted J39 through live storage/ownership guards, then updated it to J40 in place. All five payload files were unchanged and skipped. Android resolves the launcher as RoR2 Porting Lab; the owned package remains installed. Normal future iterations should preserve this installation. Persistent exception evidence now spans launches; only the known Windows shader rejection appears, and current-attempt/PID report attribution passes with zero current-PID crash entries.

All 45 original DLLs unchanged. APK SHA-256 3ccfe441ed5df653d1a3e82e6f291a33df19649226cad4e41b436c7a448d33ae. Stage/build/payload/package/device evidence archived; LAST_KNOWN_GOOD_STARTUP_LOADING_SCENE records the bounded pass. Fifteen host tests pass. Next isolate the measured component lifecycle and real recovered application host before entering Wwise; L5 menu and L5.5 simulation remain open.

Manual relaunch check: the first host check after ten seconds asserted too early while the current-PID report remained at original-first-yield with no exception. Preserve that nonterminal report and host AssertionError. A later capture from the same PID 29005 reaches segment-complete with all assertions passing; app remains installed. This is a host timing correction, not a failed game initialization or a measured second 50-second run. Future manual checks must wait for terminal phase rather than assume ten seconds is sufficient.

## J41 — Original Awake establishes the real recovered application singleton

Split L5b-3 after auditing the six component lifecycles. GlobalShaderTextures.Start binds three serialized textures; InterpolationController requires timed Start/FixedUpdate/Update; FPSQueue subscribes to application updates; two PostProcessVolume components register with a manager; NGSS_Local initializes shader globals and may need a noise resource. Activating the whole host would combine these with untested application callbacks. Instead extend J40 with explicit original Awake invocation on the actual inactive recovered application component. Require the loading flag established by the original routine; do not manufacture that flag. Original Awake therefore avoids its duplicate OnLoad coroutine branch while assigning singleton/build/type state and subscribing callbacks.

Attempt work/experiments/scene-runtime/20260913T070827.759613Z passes, Vulkan ARM64 PID 30463, 50.68 seconds. The singleton references the recovered application, AssemblyTypes includes CharacterBody, and build ID 1.0 matches lab Application.version (not the Steam content build number). The object remains inactive, all six enable-list entries remain disabled, and original filesystem globals remain null. No new initialization exception or current-PID crash appears; only the known Windows shader rejection is captured. Reviewed screenshot remains at the deliberate loading 0 percent stop. This proves an explicitly invoked original method, not automatic Unity lifecycle, full game loop, service/entitlement success or menu readiness.

All 45 original DLLs unchanged. APK SHA-256 68bad478cfbc0ac0b1076aa4adc20eedf9c1d631068c7494affa8beb009245cf. In-place update retains the owned app and skips all five unchanged payload files. Stage, component audit, build/payload/package/device evidence archived; LAST_KNOWN_GOOD_APPLICATION_AWAKE records the bounded pass. Doctor, preflight and fifteen host tests pass. Next L5b-3b invokes original GlobalShaderTextures.Start against its actual recovered component and verifies three global texture identities; rendering and other component lifecycles remain separate.

## J42 — Original global texture Start binds three recovered textures

Resolve the actual recovered component's three texture GUID/fileID pairs to unique PNG assets; preserve source hashes, names, dimensions and shader-variable expectations separately from the runtime report. Extend J41 with explicit original GlobalShaderTextures.Start on its inactive component. Save previous globals, clear only the three measured entries, invoke the unchanged original method, compare exact texture object identities and restore prior values in finally. No authored assignment of the expected textures substitutes for original Start.

Attempt work/experiments/scene-runtime/20260913T071625.955489Z passes on Vulkan ARM64, PID 31830, 51.08 seconds. _GlobalWarpRamp binds texRampCompositeLight (128×32), _EliteRamp binds texRampElites (256×128), and _SnowMicrofacetNoise binds texCloudWhitenoisePointFiltered (512×512). All runtime texture identities match measured references, all three globals match after original Start, and previous bindings restore. Application/component stay inactive; automatic lifecycle and visual shader fidelity remain unproven. Only the known Windows shader rejection is captured; zero current-PID crash entries. Screenshot remains the expected loading screen at 0 percent.

All 45 original DLL hashes unchanged. APK SHA-256 c8a10836da21c6383afffc5ee59b3a98d2ca40c22ac6be8aad1b20a62cc45cee. In-place update retained the app and skipped all five payload files. Stage, texture identities, build/payload/package/device evidence archived; LAST_KNOWN_GOOD_GLOBAL_TEXTURES records the bounded pass. Doctor, preflight and fifteen host tests pass. Next L5b-3c exercises original InterpolationController timing methods with real fixed-frame timing; FPSQueue, postprocessing and NGSS remain later isolated components.

## J43 — Original interpolation methods match real timing observations

Extend J42 with original InterpolationController.Start/FixedUpdate/Update on the actual inactive recovered component. Record real fixed and render timestamps outside the original component, check its initial fallback, compare eight results from nine distinct fixed-time samples, validate the two-entry history, and restore the previous history/index/static factor in finally. Diagnostic coroutine scheduling is explicit; no full object activation or substituted interpolation implementation.

Attempt work/experiments/scene-runtime/20260914T010129.716675Z passes, Vulkan ARM64 PID 6626, 50.11 seconds. Initial fallback is 1; all eight finite factors match the recorded timing oracle exactly, and prior state restores. Observed diagnostic sample spacing is 0.06–0.08 seconds, not every physics callback. Two factors exceed 1, consistent with original unbounded calculation under this scheduling; do not claim automatic frame-loop timing or clamp them to manufacture acceptance. Application/component remain inactive. Only the known Windows shader rejection is captured, with zero current-PID crash entries. Screenshot remains the deliberate loading 0 percent stop.

All 45 original DLLs unchanged. APK SHA-256 a8d8a8f494bbc01609e0458bddcbdef82171fb9fb4493f56c19c56a62ba084cf. Stage/timing/build/payload/package/device evidence archived; LAST_KNOWN_GOOD_INTERPOLATION records the bounded pass. Doctor, preflight and fifteen host tests pass. Next isolate FPSQueue's original initialization and callback behavior before postprocessing/NGSS. No menu, motion or simulation acceptance.

User relaxed mandatory installation retention: clean installs/cleanup are permitted when they simplify or isolate an experiment. In-place updates still work and were retained for this attempt. Choose based on the next experiment; preserve ownership, storage, evidence and any relevant profile safeguards. This supersedes earlier always-retain wording.

## J44 — FPSQueue method checks pass; unrelated foreground capture rejects acceptance

Original FPSQueue.Start on the inactive recovered component adds exactly FPSQueue.UpdateFPSLimitVars to the existing application event. The probe invokes only that newly registered callback across 36 real frames, comparing independently recorded rolling frame rates, sample/turn wraparound, throttling decisions and twelve wait-slot allocations. Previous callback registration and five mutated static fields restore. No unrelated application callbacks or full Update loop run.

Attempt work/experiments/scene-runtime/20260914T020707.371600Z reports all method assertions passing, Vulkan ARM64 PID 11995, 50.67 seconds, 36 samples, maximum averaging difference 0.00000573. Only the known Windows shader rejection is captured; no current-PID crash entries. However, visual review shows an unrelated app in the foreground. The raw runtime-result success predates the missing foreground guard and is not accepted as a complete experiment pass. assessment.json explicitly rejects visual acceptance. No passing checkpoint advances. Preserve the capture locally; do not publish it. Ask about device availability before bringing the laboratory forward while it is in use.

T08 support is now justified by this concrete failure: verify the resumed Android activity belongs to the lab package before accepting the screenshot. Persist the activity evidence locally and fail closed for absent/other foreground identity. A regression test checks that a passing runtime marker cannot mask another foreground app; all sixteen host tests pass after correcting a nonserializable mock fixture in the initial test setup. Prior fifteen-test output and initial fixture failure remain local.

All 45 original DLLs unchanged. APK SHA-256 821c584ed2cd036451cc5791882d8b1ae9c8b59be3b107fa3db3c1624a0d8a45. Stage/build/payload/package/report/capture evidence archived. App remains installed. Next collect a fresh attributable foreground verification using this same accepted build artifact when the device is available; do not rebuild unchanged game code or move on to postprocessing until capture acceptance is resolved. L5b-3d remains pending acceptance; J43 remains the last accepted component checkpoint.

## J45 — Fresh foreground verification accepts original FPSQueue proof

User confirmed the handheld was available after playing another game. Reused J44's APK and archived stage without rebuilding. Verified APK receipt/hash, all 45 original assembly hashes, live storage and payload synchronization, then cold-launched the lab and recorded a new verification directory. Original J44 runtime/capture/rejected assessment remain unchanged.

Verification work/experiments/scene-runtime/20260914T020707.371600Z/verification/20260914T021506.073430Z passes, Vulkan ARM64 PID 12977, 50.66 seconds. All 36 frame samples, callback identity, queue/throttling assertions and state/subscription restoration pass. Maximum averaging error is 0.00000382. Resumed activity is the lab package; reviewed screenshot shows the expected recovered loading screen at 0 percent. No current-PID crash or new exception; only the known Windows shader rejection remains. This establishes isolated original callback behavior, not full application Update or gameplay performance.

APK SHA-256 remains 821c584ed2cd036451cc5791882d8b1ae9c8b59be3b107fa3db3c1624a0d8a45. LAST_KNOWN_GOOD_FPS_QUEUE references the original archived stage plus this explicit accepted_verification directory. L5b-3d and the actual-device foreground check now pass; prior sixteen host tests remain applicable with no code change. Next audit the two recovered PostProcessVolume profiles and original registration/unregistration lifecycle before NGSS. Menu/audio/simulation remain open.

## J46 — First recovered postprocessing volume registration balances

Resolve the two serialized profile GUIDs and local setting file IDs; preserve their source hashes, names, priorities, six setting names and active/enabled flags. Audit original PostProcessManager construction: it discovers effect types and creates base settings. After accepted earlier component probes, verify both runtime profile identities but explicitly invoke only the first volume's original OnEnable/Update/OnDisable. Observe original manager registrations and restore the component's four mutated lifecycle fields afterward. No authored manager registration substitute or full application activation.

Attempt work/experiments/scene-runtime/20260914T022650.440781Z passes, Vulkan ARM64 PID 15023, 50.62 seconds. ppApplication_opt has the expected six settings; both profile snapshots match their measured serialized flags. Original manager initializes, registration count changes 0→1→0, original Update records weight, and component fields restore. The second ppDisabler_opt volume is inspected only. Manager base-setting initialization remains in process; only volume registrations and selected component fields are restored, not the whole manager singleton. No rendered-effect or automatic lifecycle claim.

Foreground lab identity and reviewed loading 0 percent capture pass. Only known Windows shader rejection is captured; zero current-PID crashes. All 45 original DLLs unchanged. APK SHA-256 0958bc33635e2844a076894e984f780ff5c0ece72192f26372adeee8eae06c42. Stage/profile identities/build/payload/package/device evidence archived; LAST_KNOWN_GOOD_VOLUME records this bounded pass. Doctor, preflight, sixteen host tests and staged privacy checks pass. Next test the second volume and measured priority ordering/cleanup with the first; NGSS remains separate before full startup integration.

## J47 — Both original volumes sort by priority and clean up

Extend J46 using original GrabVolumes(LayerMask), whose measured contract filters registered objects by layer and sorts ascending priority. Register the actual recovered volumes in descending order (99999 then 0), invoke original lifecycle updates, and query the actual layer plus a zero mask. No authored sorting substitutes for the original manager result. Unregister both and restore selected component fields; compare the registration and queried lists to their pre-probe baselines.

Attempt work/experiments/scene-runtime/20260914T023419.311601Z passes, Vulkan ARM64 PID 16498, 50.74 seconds. The original manager returns ppApplication_opt:0 followed by ppDisabler_opt:99999 despite reverse registration. The zero mask excludes both. Registration and query lists return to baseline, with components inactive and no instantiated profile clones. Cached manager initialization remains in process; no whole-manager reset or rendered-effect claim. Foreground lab and reviewed loading 0 percent capture pass. Only known Windows shader rejection remains; zero current-PID crashes.

All 45 original DLLs unchanged. APK SHA-256 d4baf05950d2902b996792136707fe09f75f112c6071aeb32b2a7a33ac1b5e4f. Stage/build/payload/package/device evidence archived; LAST_KNOWN_GOOD_VOLUME_ORDER records this bounded pass. Doctor, preflight and sixteen host tests pass. L5b-3f passes; the major gate remains L5 lawful startup/menu. Next inspect NGSS code provenance, serialized noise texture and shader-global initialization; then reassess integrated application startup, not just individual method calls. L5.5 simulation remains after L5.

## J48 — Locally recompiled NGSS initializes measured noise/global contract

Provenance check shows NGSS_Local is recovered source compiled into the lab Assembly-CSharp, not a preserved original DLL. Its staged hash f934a01313d1e2f12dbc7c110ba31bf8f8ad4b424d1729439f0b0a6e7c04df97 matches the recorded export. Resolve the serialized noise GUID to its PNG and record source/hash/dimensions. Derive eight expected shader values from the measured serialized fields and inspected recovered implementation. Test explicit OnEnable/Update/OnDisable on the inactive recovered component, with sentinel globals before each write phase and previous-global restoration afterward.

Attempt work/experiments/scene-runtime/20260914T024414.271681Z passes, Vulkan ARM64 PID 18598, 50.47 seconds. Runtime type belongs to Assembly-CSharp as expected. BlueNoise_R8_8 is the expected 256×256 texture; all eight globals match after initialization and update; initialization resets on disable and prior globals restore. Serialized noise is non-null, so the LegacyResourcesAPI fallback is not exercised. No rendered-shadow or automatic component lifecycle claim. Foreground lab identity and reviewed loading 0 percent capture pass; only known Windows shader rejection remains and zero current-PID crashes.

All 45 original DLLs unchanged, separately from the recompiled NGSS provenance. APK SHA-256 7eac4b5e89ab10dafa9c8623ef678a40e935bda1795ba6a3c5ad8ea2b14a75ff. Stage/provenance/noise/build/payload/package/device evidence archived; LAST_KNOWN_GOOD_NGSS records the bounded pass. Doctor, preflight and sixteen host tests pass. The listed six startup components now have isolated method evidence; do not expand that into integrated startup success.

Next L5b-4 audits all callbacks attached to the real application object, then selects a controlled integrated startup boundary. Avoid invoking Awake manually and subsequently activating the same component: original singleton handling can destroy an already initialized host. Use a fresh run and preserve real initialization ordering. Do not resume the diagnostic host's empty enable list as proof. Reassess automatic Awake/Start/Update, component enabling and the Wwise boundary with first-failure evidence. L5 menu and L5.5 simulation remain open.

## J49 — Controlled original startup activates real application callbacks

Audit the recovered host's eight MonoBehaviours, including FontCleaner outside the six-component enable list. On a fresh inactive recovered host, advance original initialization through its reviewed PreFrame phase; the original routine naturally establishes isLoading. Activate once without prior manual Awake, observe actual Unity callbacks, then externally advance the original routine through its two loading UI yields and EnableBehaviours yield. Never resume the next Wwise initialization instruction. No authored loading-state or service-success substitution.

Attempt work/experiments/scene-runtime/20260914T025708.355915Z passes on Vulkan ARM64, with 51.00 seconds of process survival. At the assertion snapshot, Start ran once, Update 95 times, FixedUpdate 174 times and LateUpdate 94 times; these are not full-run totals. The singleton matches the recovered application and all six original startup components are active. Original filesystem/cloud globals remain null. Foreground verification and reviewed screenshot agree: recovered loading UI at the deliberate 1 percent stop. Only known Windows shader rejection appears; no current-PID crash.

All 45 original DLL hashes and the APK receipt were verified. NGSS remains separately identified as locally recompiled recovered source. APK SHA-256 1eb57f565d08a737b90358d379d225a8355d352cc6a1cc11a8b0270d45e969ed. Stage, package graph, build/payload/device evidence and assessment archived; LAST_KNOWN_GOOD_INTEGRATED_STARTUP records this bounded pass. Doctor, preflight and sixteen host tests pass. The owned app remains installed. This proves automatic host callbacks within a controlled startup segment, not unrestricted startup, menu, audio, saves or character simulation. L5 remains open; next L5b-5 reviews original Wwise resource/native requirements and existing research before selecting the next experiment.

## J50 — Audio boundary audit identifies missing native runtime and unresolved prefab identities

Static audit only; no new build or device run. Reused the existing startup/prior-art research and inspected the pinned local initialization and legacy resource implementations. Original Wwise initialization schedules two asynchronous prefab loads; returning from Init is not completion evidence. LegacyResourcesAPI maps both resource names and nests load/callback accounting. Its callback checks handle validity, which alone does not prove successful status or non-null result. The next probe must assert those independently.

The accepted J49 APK contains Unity, main, Burst and IL2CPP native libraries; no separate AkSoundEngine library. The inspected preserved binding imports AkSoundEngine. AkInitializer.OnEnable reaches controller Init and IsInitialized before sound engine setup; successful managed assembly execution therefore does not establish this native boundary. No Android runtime was acquired or bank compatibility asserted.

Evidence work/experiments/audio-boundary/20260914T030831Z/audit.json records prefab hashes, serialized script references and APK native inventory. Existing editor identity evidence resolves only two AudioManager script references and none of WwiseGlobal's ten references; do not guess the remainder from names or activate the prefabs. Next resolve these identities and the initialization-settings reference, then test original legacy-path asynchronous asset loading without instantiation using the established small Android catalog. Keep original Wwise Init suspended. Separate asset loading acceptance from native/audio acceptance. J49 rollback and installed app remain unchanged; doctor passes.

## J51 — Exact-editor audio script identities resolve; serialized closure measured

Restored the accepted J49 ignored stage and verified all 45 original assembly hashes. Used the existing pinned MCP reference-identity action in the exact lab editor, without Play Mode or prefab instantiation. All seven distinct script identities resolve: AkTerminator, AkInitializer, original SoundbankLoader, AudioManager, AkGameObj, AkEvent and SetDontDestroyOnLoad. The initialization-settings asset resolves as AkWwiseInitializationSettings. Loading this ScriptableObject may execute its original OnEnable singleton registration in the editor; it is not evidence of sound-engine initialization.

Evidence work/experiments/audio-boundary/20260914T032612Z includes exact queries, returned identities, editor dispatch receipts and a hashed serialized closure: 14 files, zero unresolved external GUIDs. This covers two prefabs, four assembly files and eight settings/event assets; imported subassets and all runtime bank dependencies are not thereby validated. WwiseGlobal has AkTerminator, AkInitializer and eight SoundbankLoader components. SoundbankLoader.Start schedules each named bank, so activation is explicitly outside the next asset-only probe.

The recovered settings list six console/Windows platform entries, no Android entry. The preserved AkBasePathGetter defaults to Windows unless a custom platform-name callback overrides it. GetPlatformSettings falls back to global settings when no matching platform entry exists; absence of an Android entry alone is not a proven crash. No override, bank conversion, middleware replacement or native initialization was performed. The next device probe must test original legacy-path loading of these measured prefab assets without instantiation and independently assert status, result identity, pending-count balance and handle release.

Doctor and exact-editor identity queries pass. Stage and temporary query/helper files archived/removed; J49 APK and installed device state unchanged. No Android build/run this checkpoint, and no capability milestone advances. L5b-5a identity substep passes; device asset loading remains open.

## J52 — Original legacy-path audio prefab loads pass on Android

Added a thin audio-assets preparation action using the J51 hashed closure and existing forced build/device lifecycle. The controlled integrated startup remains stopped before Wwise. A diagnostic local catalog maps the original two legacy GUIDs to converted prefab assets in the existing separate payload. Original LegacyResourcesAPI.LoadAsync performs each load; no custom substitute loader, prefab instantiation or Wwise Init callback is used. Check independent successful status, non-null prefab identity, no scene instance, component count, pending-count balance and handle release.

Attempt work/experiments/scene-runtime/20260914T033729.020611Z passes on Vulkan ARM64, 50.11 seconds. WwiseGlobal has ten valid MonoBehaviours and AudioManager four; both original mappings and loads pass, original pending counts return to baseline, and released handles become invalid. No active AkInitializer appears. Reviewed foreground screenshot remains at the intentional loading 1 percent stop. Only the known Windows shader rejection is captured; zero current-PID crashes and no new reported exception.

All 45 original assembly hashes and APK hash verified. APK SHA-256 1f1fc3894d13cd828e72146f6f03235c9f7167ce2239f5b95ce0c101181f0e6a. Stage, source closure, build/payload/package/device evidence archived; LAST_KNOWN_GOOD_AUDIO_ASSETS records the bounded pass. Doctor, preflight, sixteen host tests and source checks pass. App remains installed. This does not prove native audio, bank compatibility, original Init callbacks, menu or simulation. Next compare authorized Android middleware availability with the measured bindings/settings; otherwise design a truthful, bounded no-audio lifecycle candidate before modifying startup. L5 remains open.

## J53 — Original native audio query confirms unavailable runtime

Checked project-local middleware artifacts: no Android Wwise runtime package/library found; this is not a claim about every host directory or vendor access. Extended the J52 asset probe with one original AkSoundEngine.IsInitialized call. Catch only DllNotFoundException as the predicted absent-library outcome and explicitly report AudioUnavailable; an entry-point error or returned status fails this hypothesis. Do not initialize Wwise, instantiate either prefab, load banks or return fabricated AK success.

Attempt work/experiments/scene-runtime/20260914T034427.544344Z confirms the hypothesis on Vulkan ARM64, 51.00 seconds. Both original prefab asset checks still pass and the native query reports AudioUnavailable:DllNotFoundException. The caught expected exception is recorded as an observation, not a sound capability pass. Foreground screenshot reviewed at loading 1 percent; no current-PID crash or new unhandled exception. Known Windows shader rejection remains.

All 45 original DLLs unchanged; APK SHA-256 61a64ac199ba888fe001b1b8645a97001a0fe280618e46f83a57fb889f489921. Stage, contract/source hashes, build/payload/package/device evidence and assessment archived. J52 remains the accepted audio-asset rollback; no audio capability pointer advances. Doctor, preflight and sixteen tests pass. App remains installed.

Next candidate: an explicit unavailable-audio policy at the early initializer call, preserving the remainder of the original coroutine and stopping at its Addressables yield before filesystem/platform setup. Measure and input-gate the exact transformation before applying it; record the transformed assembly separately from originals. This is not yet implemented or a complete no-audio lifecycle. Later original status-query/Windows error-dialog handling and bank pending waits remain obligations before unrestricted startup. No mandatory platform/ownership checks may be bypassed.

## J54 — Audio guard preparation fails before candidate creation

Attempt work/experiments/scene-runtime/20260914T035112.137650Z fails while Cecil writes metadata without an original managed-assembly resolver path. The shell also dispatched a build after failed preparation; it completed but is explicitly rejected as guard evidence and was never installed. Failed preparation, invalid build receipt and stage are preserved. No passing pointer advances. Revisit with the accepted original managed directory in the resolver and dispatch builds only after separately verified successful preparation.

## J55 — Early explicit no-audio guard reaches the original Addressables yield

The revised resolver permits a distinct local assembly candidate. Input SHA and exact two-instruction static Boolean getter contract are checked before changing ldc.i4.0 to ldc.i4.1 in WwiseIntegrationManager.get_noAudio. The original initializer remains intact and follows its existing optional-audio branch. Wrong-input and already-transformed rejection checks pass; metadata comparison of the target type finds only the getter body changed. The full candidate hash is recorded separately; no native success or platform/ownership change is introduced.

Attempt work/experiments/scene-runtime/20260914T035253.268343Z passes on Vulkan ARM64, 51.14 seconds. The actual original routine advances through its post-audio frame yield and Addressables initialization yield. Addressables was already initialized by the diagnostic audio-asset probe, so this proves the original subsequent call completes, not first-time unassisted catalog startup. Filesystem/cloud globals remain null and no AkInitializer activates. Original native query still reports unavailable. Reviewed foreground screenshot shows the deliberate 2 percent stop; no current-PID crash or new unhandled exception, only known Windows shader rejection.

Forty-four original DLLs remain unchanged; RoR2.dll is the recorded single-getter candidate. APK SHA-256 b41677fb52eb11cafc75fd3651fdb7808f0914ebb21fc7d51b0f4d63d708e574. Stage, original/candidate assemblies, transformation/negative-test records and build/payload/package/device evidence archived. LAST_KNOWN_GOOD_EARLY_NO_AUDIO records this bounded pass; J52 original-assembly rollback remains. Doctor, preflight and sixteen tests pass. This is not complete no-audio lifecycle or L5 acceptance. Next audit the coupled filesystem and PlatformSystems segment before resuming; later native-query/dialog and bank-wait obligations remain open.

## J56 — Diagnostic filesystem assignment fails compilation

Attempt work/experiments/scene-runtime/20260914T040044.868154Z fails with CS0200: RoR2Application.fileSystem has a private setter. No device installation occurred. Build/editor evidence and stage are preserved. The corrected candidate invokes the measured original private setter through reflection; no visibility rewrite or substituted backing field.

## J57 — Original configuration methods work with temporary Android filesystem globals

Consumer audit corrects the path policy: fileSystem supports Config writes, run history and bad-profile logs, while cloudStorage supports UserProfiles and per-user configuration. Read-only payload content must remain a third, separate concern. PlatformSystems.Init calls SteamworksClientManager before its crossplay branch and installs concrete save/achievement/entitlement implementations; toggling crossplay is not an offline adapter. Do not resume that coupled segment.

Attempt work/experiments/scene-runtime/20260914T040151.193531Z passes on Vulkan ARM64, 50.13 seconds. At the accepted pre-platform stop, the harness invokes the original filesystem setter and temporarily assigns cloudStorage to a separate owned writable root. Original Console.WriteConfigFile writes a config sentinel, original StreamingAssetsTextDataManager.GetConfFile reads it exactly, and the same writer writes a distinct profile-root sentinel. Isolation assertions pass, original globals restore to null and the unique owned test directory is removed. No console command execution, profile serialization or platform initialization occurs. The text-manager constructor's Application.dataPath configFolder remains unchanged and is not used by the tested GetConfFile path.

Foreground screenshot reviewed at 2 percent; no current-PID crash or new exception, only known Windows shader rejection. Forty-four original DLLs unchanged; RoR2 retains only the prior no-audio getter candidate. APK SHA-256 9b9c1b68e50b386423bfaa92ea8dd356e7f576184493c8a8e9e8d2345125ad68. Stage, consumer/source-hash audit and build/payload/package/device evidence archived; LAST_KNOWN_GOOD_CONFIG_BINDING records the bounded proof. Doctor, preflight and sixteen tests pass. Next audit exact platform/entitlement startup contracts and select a truthful boundary; actual vanilla profile and full no-audio lifecycle acceptance remain separate.

## J58 — Original Steam load callback returns false on Android

Exact-input audit corrects earlier shorthand: SteamworksClientManager.Init registers callbacks; client construction happens only in loadSteamworksClient. The non-editor constructor validates the client, restart/API validator and base-game subscription before installing remote storage. DLC checks use the original entitlement resolver separately. SaveSystemSteam's constructor only marks initial-load state; its name alone does not make every method native. Startup's recorded failed-load path shows a failure dialog instead of normal profile loading. Preserve these checks and outcomes.

Attempt work/experiments/scene-runtime/20260914T041353.880600Z executes original Init, load and unload with no existing manager, profile globals or relative app-id file. The callback returns false, unload leaves no manager and globals remain null; prior callbacks restore. Vulkan ARM64, 51.08 seconds, reviewed foreground loading 2 percent, no current-PID crash or new unhandled exception. Only known Windows shader rejection remains. This is a discriminating failed platform result, not platform capability acceptance. The original catch obscures its cause; false does not prove that a subscription check ran or failed.

Forty-four original DLLs unchanged; RoR2 retains only the previous no-audio getter candidate, with Steam code unchanged. APK SHA-256 193f9666da1b1aef194cac53609fcf3a8c987c662623945989d16de902bbd97b. Stage, exact-input platform audit and build/payload/package/device evidence archived. J57 remains the accepted configuration rollback; no platform-success pointer advances. Doctor, preflight and sixteen host tests pass; app remains installed. Next add only the necessary caught-failure observation while preserving return value, control flow and mandatory checks. No legitimate Android authenticated/ownership route has been demonstrated; dependent gameplay startup remains stopped.

## J59 — Second constructor diagnostic observes contaminated state, not first failure

Attempt work/experiments/scene-runtime/20260914T052702.565501Z first repeats the original false callback, then invokes the original private constructor through reflection. It reports an existing Facepunch client singleton. This reveals incomplete constructor state retained below the RoR2 manager after the earlier failed load; original manager unload does not establish whole-library cleanup. Runtime assertions pass, but assessment rejects root-cause attribution. Preserve this attempt; no capability pointer advances. Revised hypothesis requires a first constructor invocation in a fresh process, without a preceding load callback.

## J60 — Fresh constructor identifies Windows Steam native backend on Android

Attempt work/experiments/scene-runtime/20260914T053016.404814Z starts with null Facepunch client/manager and null filesystem globals, then directly invokes the unchanged original private constructor. Reflection exposes System.DllNotFoundException for steam_api64.dll through SteamNative.Platform.Win64.Native.SteamAPI_Init, Facepunch native InitClient and the original constructors. This is the first invocation in the process. The subscription/API validation checks later in the constructor have not been reached. Do not infer failed ownership or substitute success. This mode does not invoke the normal load callback; its default report Boolean is not new callback evidence (J58 remains that evidence).

Vulkan ARM64, 50.60 seconds, reviewed foreground loading 2 percent, no current-PID crash or new unhandled exception. Expected caught exception remains in the dedicated report; generic logs contain only known Windows shader rejection. A failed Facepunch construction can leave partial static state, so repeated constructor attempts in one process are invalid for first-failure attribution.

Forty-four original DLLs unchanged; RoR2 retains only the earlier no-audio getter candidate. No Steam instrumentation patch was needed. APK SHA-256 a3476bd5bcdc649a749e618525e5f54a17bd476668e5676a7ec595efd70ee0fa. Stage, build/payload/package/device evidence and causal assessment archived. Doctor, preflight and sixteen tests pass. J57 remains accepted configuration rollback; no platform-success pointer advances. Next assess a legitimate compatible platform runtime or authorized port integration against this concrete native dependency and mandatory checks. Do not blindly switch backend strings, use successful fake services, or repeat unchanged failed constructors. Independent profile/content experiments may continue while gameplay startup is held at the platform boundary.
