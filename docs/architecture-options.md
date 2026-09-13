# Architecture experiments

These are laboratory proofs, not a finished port. No original game startup, authentication, entitlement or profile logic was bypassed.

## A — mostly reconstructed source/project

Full AssetRipper 2.0.0 export completed locally with exact Unity 2021.3.33f1, 86 scene files and approximately 12 GiB of generated project content before the Library cache. The default exporter actually preserves 53 DLLs and emits only 23 source files; therefore this export is **not** proof of full C# reconstruction. Its first editor compile exposed four ambiguous-type errors; a bounded qualification patch removes those first errors. After patching, the complete project imported in about 355 seconds and connected through MCP. Its loadingbasic scene loads with 64 GameObjects and no missing-script components in that scene. Entering Play Mode crashes natively in Burst/Collections initialization. A minimal Android scene build against the exported assembly closure ran for about 296 seconds and failed in IL2CPP VTable construction; offending type definitions map to Rewired_Core and Rewired_Windows. No reconstructed APK was produced.

A separate full RoR2 C# reconstruction test decompiled every type to 3,851 files. Both current Roslyn and the exact editor's C# 9 compiler report **11 unique errors** with C#9-compatible decompiler output: CS0053 (4), CS0507 (4), CS0122 (2), CS0104 (1). This is a first compiler pass, not a guarantee only 11 fixes remain. No attempt to rewrite gameplay was made. Source export is recoverable enough to remain the fallback.

## B — player/content surgery

A Windows Mono player/native plugin set cannot execute natively on ARM64 Android. The compatible supported laboratory player is rebuilt with Unity IL2CPP. Original managed DLLs may be inputs to that build; they do not remain dynamically executable Mono DLLs in the finished APK. The concrete preservation proof executes the original installed SimpleJSON.dll's parsing API after IL2CPP AOT on the real device.

An original Windows shader bundle was synced independently and rejected by the GLES3 Android player. This disproves the simplest unchanged-content variant for that sample. Inventory independently establishes D3D11-only programs throughout the scanned shaders. Pure unchanged Windows-player/content surgery is rejected as the primary approach. A narrower precompiled-assembly path is retained inside C.

## C — hybrid (preferred)

A clean source-owned Android harness imports the exact installed SimpleJSON.dll, converts an original Commando grenade mesh to OBJ locally, imports it with the pinned Unity editor, and builds an Android LZ4 bundle. The ARM64 APK executes the preserved assembly and loads the separately synced bundle on adopted storage. Screenshot inspection confirms visible game-derived geometry with a replacement Unity Standard material. The original mesh has 261 vertices in the runtime proof. It is not a rigged character or original scene.

GLES3 proof: `work/runs/20260913T011048.134293Z-7630bdfebf6b/`. Check the journal/state for additional Vulkan proof. This validates the conversion/AOT/storage/diagnostics boundaries while leaving the difficult RoR2 closure and service seams explicit.

## Comparative score

Scores are engineering judgments (INFERRED), 1 poor to 5 favorable; they are not performance measurements. Generated material score rewards a smaller local generated footprint. All approaches must retain the user-supplied-input distribution model.

| Criterion | A source reconstruction | B unchanged surgery | C hybrid |
| --- | ---: | ---: | ---: |
| Technical feasibility | 3 | 1 | 4 |
| Generated proprietary footprint | 1 | 4 | 3 |
| Build reproducibility | 3 | 2 | 4 |
| Update resilience | 2 | 2 | 4 |
| Graphics fidelity potential | 4 | 1 | 4 |
| Native plugin complexity (higher easier) | 2 | 1 | 2 |
| Agent automation | 3 | 2 | 5 |
| Incremental speed | 2 | 4 | 4 |
| Debugging quality | 5 | 2 | 4 |
| Maintainability | 2 | 2 | 4 |
| Clean tooling-only redistribution | 5 | 5 | 5 |

C's score is conditional: preserving the full original dependency closure currently fails; selective replacement of the Rewired platform integration is required before that proof can advance. If those fail persistently, A becomes the fallback. None of these scores authorizes redistributing game content or licensed middleware.

Vulkan also passes: `work/runs/20260913T012337.819186Z-46130c90d7a1/`. Both APIs reject the original Windows shader bundle. A filesystem GUID scan found 173 unresolved external GUIDs across 43,168 YAML files / 943,831 references. This is not a complete local-fileID or package-reference audit. Scene-level zero missing scripts does not contradict unresolved references elsewhere.
