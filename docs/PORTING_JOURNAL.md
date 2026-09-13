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
