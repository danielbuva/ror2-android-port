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
