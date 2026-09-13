# Execution backlog

Canonical policy: DEVELOPMENT_PLAN.md. Immediate order: T01 → T02 → T05 → T06 → T07. Conditional tooling needs a named triggering experiment. A completed experiment is not necessarily a passed capability gate.

Every record uses the required issue schema. All outputs containing game-derived data remain ignored. Future tasks must be split from the measured first failure, not speculative downstream fixes.

## T01 — Reproduce and preserve baseline
- **ID:** T01
- **TITLE:** Reproduce and preserve baseline
- **STATUS:** DONE
- **CONTEXT:** L0–L3 execution, or conditional supporting gate per DEVELOPMENT_PLAN.md.
- **OBSERVATION:** Historical utility/G2 proof; fresh baseline required.
- **HYPOTHESIS:** Existing Vulkan proof remains reproducible.
- **TASK:** Run doctor, preflight, test and Vulkan smoke; verify ABI, placement, markers, visual geometry and cleanup; preserve rollback and approved documents.
- **CONSTRAINTS:** AGENTS.md and DEVELOPMENT_PLAN.md; original input immutable; exact tools/device; no false ownership/auth; serialize editor; first-failure discipline.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing workflow, docs, ignored checkpoints.
- **TEST COMMAND:** ./dev doctor; ./dev preflight; ./dev test; ./dev smoke --target vulkan. Proposed actions must be added and documented before use.
- **PASS CONDITION:** Fresh device G2 pass, recoverable known-good APK/payload.
- **FAILURE EVIDENCE TO CAPTURE:** First failed check, APK identity, run and live storage; immutable attempt logs/result and relevant visual evidence.
- **STATE/JOURNAL UPDATES REQUIRED:** PORTING_STATE after meaningful progress; journal on failure with revisit condition; milestone/backlog at gates; reviewed logical commit.
- **DEPENDENCIES:** None.

## T02 — Identify smallest meaningful RoR2 slice
- **ID:** T02
- **TITLE:** Identify smallest meaningful RoR2 slice
- **STATUS:** DONE
- **CONTEXT:** L0–L3 execution, or conditional supporting gate per DEVELOPMENT_PLAN.md.
- **OBSERVATION:** SimpleJSON does not prove RoR2; J09 identifies Rewired conflicts.
- **HYPOTHESIS:** A bounded dependency transformation enables actual original game code.
- **TASK:** Attribute conflicting metadata and consumers; select an independently checkable RoR2/EntityStates probe; record dependency/roots/contracts and early mandatory service risks.
- **CONSTRAINTS:** AGENTS.md and DEVELOPMENT_PLAN.md; original input immutable; exact tools/device; no false ownership/auth; serialize editor; first-failure discipline.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Managed inventory, local recovered source, narrow analysis.
- **TEST COMMAND:** Existing reports; ./dev prototype --action dependency-boundaries if needed. Proposed actions must be added and documented before use.
- **PASS CONDITION:** Exact original methods, assertions, required types/native references and first candidate recorded.
- **FAILURE EVIDENCE TO CAPTURE:** Unresolved signatures, conflicting definitions, access/native contracts; immutable attempt logs/result and relevant visual evidence.
- **STATE/JOURNAL UPDATES REQUIRED:** PORTING_STATE after meaningful progress; journal on failure with revisit condition; milestone/backlog at gates; reviewed logical commit.
- **DEPENDENCIES:** T01.

## T05 — Isolate Rewired boundary
- **ID:** T05
- **TITLE:** Isolate Rewired boundary
- **STATUS:** BOUNDED AOT PASS; controller/native integration OPEN
- **CONTEXT:** L0–L3 execution, or conditional supporting gate per DEVELOPMENT_PLAN.md.
- **OBSERVATION:** Windows closure conflicts in Core/Windows.
- **HYPOTHESIS:** Android-capable integration retains required contract.
- **TASK:** Test authorized compatible package first; compare consumed API/serialized identity. If unavailable assess one bounded adapter, not a speculative replacement middleware.
- **CONSTRAINTS:** AGENTS.md and DEVELOPMENT_PLAN.md; original input immutable; exact tools/device; no false ownership/auth; serialize editor; first-failure discipline.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Generated middleware, import config, transforms and probe.
- **TEST COMMAND:** Experiment-specific ./dev action and existing forced build/lifecycle. Proposed actions must be added and documented before use.
- **PASS CONDITION:** Known conflicts removed with required types exercised, not stripped away.
- **FAILURE EVIDENCE TO CAPTURE:** VTable, API/type differences, native load and init; immutable attempt logs/result and relevant visual evidence.
- **STATE/JOURNAL UPDATES REQUIRED:** PORTING_STATE after meaningful progress; journal on failure with revisit condition; milestone/backlog at gates; reviewed logical commit.
- **DEPENDENCIES:** T02; minimum triggered support.

## T06 — Isolate Burst/Collections
- **ID:** T06
- **TITLE:** Isolate Burst/Collections
- **STATUS:** REPRESENTATIVE PACKAGE PASS; full game compatibility OPEN
- **CONTEXT:** L0–L3 execution, or conditional supporting gate per DEVELOPMENT_PLAN.md.
- **OBSERVATION:** J05 direct-call initialization crashes editor.
- **HYPOTHESIS:** Compatible artifacts or valid managed fallback preserve operations.
- **TASK:** Inspect fingerprints/direct calls; one justified package candidate then separate fallback if needed; allocation/disposal and job/hash probe.
- **CONSTRAINTS:** AGENTS.md and DEVELOPMENT_PLAN.md; original input immutable; exact tools/device; no false ownership/auth; serialize editor; first-failure discipline.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Generated packages/imports and probe.
- **TEST COMMAND:** Experiment-specific ./dev action, guarded editor and Android probes. Proposed actions must be added and documented before use.
- **PASS CONDITION:** Expected results without crashes; editor/device classified separately.
- **FAILURE EVIDENCE TO CAPTURE:** Package graph, API/layout/direct call and crash stack; immutable attempt logs/result and relevant visual evidence.
- **STATE/JOURNAL UPDATES REQUIRED:** PORTING_STATE after meaningful progress; journal on failure with revisit condition; milestone/backlog at gates; reviewed logical commit.
- **DEPENDENCIES:** T02; normally after T05.

## T07 — Execute meaningful original code on Android
- **ID:** T07
- **TITLE:** Execute meaningful original code on Android
- **STATUS:** BOUNDED SLICE PASS; full closure OPEN
- **CONTEXT:** L0–L3 execution, or conditional supporting gate per DEVELOPMENT_PLAN.md.
- **OBSERVATION:** Utility execution does not prove game code.
- **HYPOTHESIS:** Selected boundary permits original slice AOT and execution.
- **TASK:** Stage slice in existing lab; root methods, forced build, guarded install and assert results; unchanged originals distinguished from transforms.
- **CONSTRAINTS:** AGENTS.md and DEVELOPMENT_PLAN.md; original input immutable; exact tools/device; no false ownership/auth; serialize editor; first-failure discipline.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Lab probe, original assemblies, preservation and targeted transforms.
- **TEST COMMAND:** ./dev prototype --action ror2-slice (thin existing lifecycle; add when needed). Proposed actions must be added and documented before use.
- **PASS CONDITION:** Three cold launches ≥30 seconds each with correct original method results.
- **FAILURE EVIDENCE TO CAPTURE:** AOT, preservation/assembly hashes, assertions, crashes/exceptions; immutable attempt logs/result and relevant visual evidence.
- **STATE/JOURNAL UPDATES REQUIRED:** PORTING_STATE after meaningful progress; journal on failure with revisit condition; milestone/backlog at gates; reviewed logical commit.
- **DEPENDENCIES:** T05 and device-relevant T06 outcome.

## T03 — Build attribution and installation safety
- **ID:** T03
- **TITLE:** Build attribution and installation safety
- **STATUS:** CONDITIONAL
- **CONTEXT:** L0–L3 execution, or conditional supporting gate per DEVELOPMENT_PLAN.md.
- **OBSERVATION:** Next experiment cannot identify completion or safe package identity.
- **HYPOTHESIS:** A narrow receipt/guard removes the concrete ambiguity.
- **TASK:** Add only needed attempt/terminal receipt or guard; keep separate reconstruction APK host-only.
- **CONSTRAINTS:** AGENTS.md and DEVELOPMENT_PLAN.md; original input immutable; exact tools/device; no false ownership/auth; serialize editor; first-failure discipline.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Build/editor/device orchestration.
- **TEST COMMAND:** ./dev test and triggering experiment. Proposed actions must be added and documented before use.
- **PASS CONDITION:** Stale output/failed dispatch/wrong-package cases rejected as applicable.
- **FAILURE EVIDENCE TO CAPTURE:** Attempt/progress and identity evidence; immutable attempt logs/result and relevant visual evidence.
- **STATE/JOURNAL UPDATES REQUIRED:** PORTING_STATE after meaningful progress; journal on failure with revisit condition; milestone/backlog at gates; reviewed logical commit.
- **DEPENDENCIES:** Trigger required; not wholesale prerequisite.

## T04 — Cache and independent data identities
- **ID:** T04
- **TITLE:** Cache and independent data identities
- **STATUS:** CONDITIONAL
- **CONTEXT:** L0–L3 execution, or conditional supporting gate per DEVELOPMENT_PLAN.md.
- **OBSERVATION:** Scene cache uncertain or content edit rebuilds unchanged AOT.
- **HYPOTHESIS:** Affected recipe fix avoids stale reuse/unneeded builds.
- **TASK:** Force build initially; fix relevant recipe inputs or separate content receipt/build when needed.
- **CONSTRAINTS:** AGENTS.md and DEVELOPMENT_PLAN.md; original input immutable; exact tools/device; no false ownership/auth; serialize editor; first-failure discipline.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Build/cache/content tooling.
- **TEST COMMAND:** Targeted scene/code/content change test. Proposed actions must be added and documented before use.
- **PASS CONDITION:** Changed scenes invalidate; pure content avoids unnecessary AOT once supported.
- **FAILURE EVIDENCE TO CAPTURE:** Input/output hashes and cache decisions; immutable attempt logs/result and relevant visual evidence.
- **STATE/JOURNAL UPDATES REQUIRED:** PORTING_STATE after meaningful progress; journal on failure with revisit condition; milestone/backlog at gates; reviewed logical commit.
- **DEPENDENCIES:** Trigger from immediate experiment.

## T08 — Subsystem observability
- **ID:** T08
- **TITLE:** Subsystem observability
- **STATUS:** CONDITIONAL
- **CONTEXT:** L0–L3 execution, or conditional supporting gate per DEVELOPMENT_PLAN.md.
- **OBSERVATION:** Next failure cannot be classified from current file diagnostics.
- **HYPOTHESIS:** One typed observation identifies first failure.
- **TASK:** Add only needed init/scene/reference/authority/input report; bind current launch.
- **CONSTRAINTS:** AGENTS.md and DEVELOPMENT_PLAN.md; original input immutable; exact tools/device; no false ownership/auth; serialize editor; first-failure discipline.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Diagnostics and collector.
- **TEST COMMAND:** Triggering experiment plus stale/failure fixture where applicable. Proposed actions must be added and documented before use.
- **PASS CONDITION:** Current attempt state distinguishes expected failure.
- **FAILURE EVIDENCE TO CAPTURE:** Event/state and launch correlation; immutable attempt logs/result and relevant visual evidence.
- **STATE/JOURNAL UPDATES REQUIRED:** PORTING_STATE after meaningful progress; journal on failure with revisit condition; milestone/backlog at gates; reviewed logical commit.
- **DEPENDENCIES:** Trigger from immediate experiment.

## T10 — Storage scale
- **ID:** T10
- **TITLE:** Storage scale
- **STATUS:** CONDITIONAL
- **CONTEXT:** L0–L3 execution, or conditional supporting gate per DEVELOPMENT_PLAN.md.
- **OBSERVATION:** Tiny payload does not prove multi-GiB behavior.
- **HYPOTHESIS:** Adopted split supports realistic content size.
- **TASK:** Before large content use realistic synthetic payload; interrupt/retry/hash/update/unchanged sync/owned cleanup; stage dependent generations before activation.
- **CONSTRAINTS:** AGENTS.md and DEVELOPMENT_PLAN.md; original input immutable; exact tools/device; no false ownership/auth; serialize editor; first-failure discipline.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Sync/lifecycle and synthetic fixture.
- **TEST COMMAND:** ./dev storage; experiment-specific scale action. Proposed actions must be added and documented before use.
- **PASS CONDITION:** Verified hashes, no incomplete activation, unchanged transfer skipped, retention and owned cleanup.
- **FAILURE EVIDENCE TO CAPTURE:** Capacity before/during/after, backing, partial state, transfer time; immutable attempt logs/result and relevant visual evidence.
- **STATE/JOURNAL UPDATES REQUIRED:** PORTING_STATE after meaningful progress; journal on failure with revisit condition; milestone/backlog at gates; reviewed logical commit.
- **DEPENDENCIES:** Immediately before large content.

## T01 evidence

Passed fresh doctor/preflight, six safety tests and Vulkan smoke. work/runs/20260913T020341.114229Z-46130c90d7a1; screenshot reviewed; package removed. Runtime pointer: work/checkpoints/LAST_KNOWN_GOOD_RUNTIME.json.

## Subsequent issue expansion

L4: required reference closure → animated prefab → loadingbasic device load. L5/L9: writable profile root → observed lawful startup boundary → menu. L5.5: master/body spawn/authority → deterministic original simulation → built-in input. L6: stage integration → camera/abilities. L7: enemy/damage → pickup/interactable → director → teleporter. L8: transitions/lifetime → finale → victory persistence. Expand each into this full schema only when its prerequisite evidence exists.

## T02 result / T05 candidate refinement

J11 attributes both conflicts to extra exported forwarding getters; original DLL bytes have one implementation per slot. Evidence: work/experiments/dependency-boundaries/20260913T021130.995984Z. T05 first tests original DLLs with the actual disputed types rooted/invoked. T07 selected Trajectory and ProcChainMask/ProcType; slice success is not full closure acceptance.

T05/J12: original Core/Windows bytes pass both explicitly rooted conflicting virtual slots on device, work/experiments/rewired-original/20260913T021247.788313Z. T06 next.

## Next gate refinement — T07b

T07 passes at work/experiments/ror2-slice/20260913T022358.230312Z. Before L4, AOT-build the full original managed set with compatible packages. This distinguishes actual assembly preservation from the export-modified J09 closure; do not infer full closure from a type-pruned slice.

## T07b — Full original managed-set AOT
- **ID:** T07b
- **TITLE:** Full original managed-set AOT
- **STATUS:** PASS — full AOT and additional baseline device smoke (J18)
- **CONTEXT:** J12 original Rewired slots and J14 package candidate pass; J16 type-pruned RoR2 slice passes.
- **OBSERVATION:** J09 tested export-modified DLLs; a type-pruned slice does not prove full closure.
- **HYPOTHESIS:** Original DLL bytes with the tested package providers can AOT-build the full RoR2 assembly.
- **TASK:** Stage original dependencies in existing lab, explicitly root full RoR2, resolve package modules, force build, attribute the first failure. No startup/auth adapters.
- **CONSTRAINTS:** Common plan; never substitute an export-only library without checking original consumers; preserve stage/input hashes and failed evidence. Wait for terminal build before any editor mutation.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Thin ./dev experiment runner, ignored lab stage, original dependency manifest and build receipts.
- **TEST COMMAND:** ./dev prototype --action original-closure-prepare; resolve pinned modules; ./dev prototype --action original-closure-build.
- **PASS CONDITION:** Terminal ARM64 IL2CPP APK build, staged input hashes retained and full RoR2 rooted. This is not device/startup acceptance.
- **FAILURE EVIDENCE TO CAPTURE:** Original dependency hashes, package providers, first error, full relevant editor build output; no APK installed on build failure.
- **STATE/JOURNAL UPDATES REQUIRED:** State and J17 onward, backlog/milestone status; next runtime experiment only after measured build outcome.
- **DEPENDENCIES:** T05/T06/T07 bounded passes.

## T07c — Original method assertions with the full assembly
- **ID:** T07c
- **STATUS:** PASS — J20, three full-original launches
- **TITLE:** Repeat bounded game assertions without type pruning
- **CONTEXT:** J16 passes a type-pruned slice; J18 full original assembly builds and survives baseline smoke.
- **OBSERVATION:** Full assembly has not yet run the ten explicit trajectory/proc assertions.
- **HYPOTHESIS:** The full unchanged DLL produces the same results without extra runtime initialization failures.
- **TASK:** Reuse the existing authored assertion probe with the staged full assembly, record full-original identity, force build and run three cold launches.
- **CONSTRAINTS:** Common contract; only one RoR2.dll, no startup/auth patches; do not mistake LAB_READY for game readiness.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing probe and thin runner; ignored full assembly stage and receipts.
- **TEST COMMAND:** ./dev prototype --action original-closure-runtime; existing preflight/build/install/capture lifecycle.
- **PASS CONDITION:** Ten assertions on each of three distinct cold PIDs surviving ≥30 seconds, unchanged full DLL hash, no unexplained managed/native failures.
- **FAILURE EVIDENCE TO CAPTURE:** Current-launch assertion file, initialization errors, crash output, full assembly hashes and terminal build result.
- **STATE/JOURNAL UPDATES REQUIRED:** Record outcome and L3 scope; advance to L4 reference closure only after classification.
- **DEPENDENCIES:** T07b; no new broad infrastructure.

## L4a — Required recovered reference closure
- **ID:** L4a
- **STATUS:** COMPLETE — discriminating editor audit J21; device L4 remains OPEN
- **TITLE:** Audit loadingbasic and one dependency-rich prefab
- **CONTEXT:** L3 full-original method execution passes.
- **OBSERVATION:** G2 only renders a static recovered mesh; no original scene has loaded.
- **HYPOTHESIS:** A bounded recovered scene/prefab closure can retain required script and asset identities.
- **TASK:** Use existing reference reports and original/export metadata to identify required GUIDs, file IDs, script types, subassets, catalog locations, rig/animation and material dependencies; select the smallest closure and first repair.
- **CONSTRAINTS:** Common contract; no large transfers before T10; do not infer reference integrity from a loaded bundle container.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing reference tooling and ignored closure report; narrow transformation only if a concrete defect is found.
- **TEST COMMAND:** ./dev prototype --action references; inspect existing command scope before extending it; ./dev preflight before any build.
- **PASS CONDITION:** Exact required closure, unresolved references and next discriminating scene/prefab build are recorded. Device scene acceptance remains a separate L4 experiment.
- **FAILURE EVIDENCE TO CAPTURE:** First required missing/mismatched reference, source/export identities, catalog/provider dependencies and estimated payload size.
- **STATE/JOURNAL UPDATES REQUIRED:** Update L4 status and first experiment; preserve prior runtime receipt.
- **DEPENDENCIES:** T07c/L3.

## L4b — First loadingbasic Android scene bundle
- **ID:** L4b
- **STATUS:** BOUNDED DEVICE PASS — J23; complete L4 acceptance remains open
- **TITLE:** Import and load the measured loading scene closure
- **CONTEXT:** L4a/J21 yields a small closure and matching original DLL script IDs.
- **OBSERVATION:** 122 files, roughly 10 MiB source closure; dynamic fallback atlas missing; no Android scene proof.
- **HYPOTHESIS:** Original GUID/fileID preservation plus measured package UI remapping enables scene import and Android serialization.
- **TASK:** Stage only loadingbasic closure and original managed providers. Resolve each consumed UI type to its package MonoScript and rewrite only measured references. Validate missing scripts/references before building a separate Android scene bundle. Load through the existing lab, collect scene/error/capture evidence.
- **CONSTRAINTS:** Common contract; force builds for changed scenes; serialized editor operations must finish before another dispatch. Do not invoke RoR2Application or platform startup to repair an unmeasured scene error. Do not overwrite baseline APK/payload receipts.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Ignored closure/meta staging, narrow identity transform and scene probe; existing lab bundle/build lifecycle.
- **TEST COMMAND:** Add a thin scene-runtime prototype action when staging begins; ./dev preflight, forced Vulkan build, existing device lifecycle.
- **PASS CONDITION:** Real device loads original loadingbasic scene with resolved required scripts, traceable dependencies and visually reviewed capture. Record fallback font and placeholder material limitations; dependency-rich prefab remains a separate L4 subgate.
- **FAILURE EVIDENCE TO CAPTURE:** Import identity mismatch first, then bundle/build errors, scene activation exceptions, dynamic atlas behavior, current-launch screenshot.
- **STATE/JOURNAL UPDATES REQUIRED:** J22 onward; preserve L3 rollback; advance no scene pointer on failed import or mere bundle container success.
- **DEPENDENCIES:** L4a. T10 not yet triggered by measured small closure; check actual built size.

## L4c — Complete object audit and dependency-rich prefab content
- **ID:** L4c
- **STATUS:** BOUNDED DEVICE PASS — J24/J26; persistent objects and inactive prefab rig integrity proven
- **TITLE:** Extend the measured scene proof to persistent objects and prefab content
- **CONTEXT:** J23 loads the original loading scene with application startup inactive.
- **OBSERVATION:** Current count omits objects moved to DontDestroyOnLoad; Commando closure is measured but not instantiated.
- **HYPOTHESIS:** Original serialized identities remain valid across persistent objects and a recovered prefab dependency closure.
- **TASK:** Add the missing scene/persistent-object observation to the existing probe; inspect required font/render/animation references. Then introduce an inactive dependency-rich prefab for component/rig/material audit before any original character simulation. Split runtime animation into its own assertion if needed.
- **CONSTRAINTS:** Common contract; startup stays inactive, no authority/gameplay claim, no large unmeasured transfer. Fix first reference/import failure before later behavior.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing LoadingSceneProbe and narrowly staged content; no general observability framework.
- **TEST COMMAND:** Existing scene-prepare/identity/scene-arm/forced Vulkan build/scene-run flow, extended only for this probe.
- **PASS CONDITION:** Required components accounted for across loaded and persistent objects; prefab script/rig/animation/material references resolve on device and capture agrees. Complete L4 only when all its required assertions pass.
- **FAILURE EVIDENCE TO CAPTURE:** Persistent-object linkage, first missing required component/subasset, exceptions, actual font/animation observations and capture.
- **STATE/JOURNAL UPDATES REQUIRED:** Preserve J23 receipt and L3 rollback; distinguish content, startup and simulation gates.
- **DEPENDENCIES:** L4b bounded result.

## L4d — Visible recovered Commando content
- **ID:** L4d
- **STATUS:** PASS — J28 paired visual poses and bone changes; L4 isolated content accepted
- **TITLE:** Validate visible pose and animation of recovered character content
- **CONTEXT:** J26 proves inactive prefab component/rig identities with six diagnostically bound default assets.
- **OBSERVATION:** The character is intentionally inactive and absent from captures; 35 clips and a valid avatar are present but not sampled.
- **HYPOTHESIS:** The validated skeleton/mesh/animation data can produce a recognizable pose and changing animation on device without activating gameplay scripts.
- **TASK:** Extend only the existing content probe to display the recovered model and sample a bounded animation. Keep original gameplay behaviours/startup isolated; explicitly distinguish diagnostic pose/rendering from original state-machine simulation. Inspect the first actual material/animation mismatch.
- **CONSTRAINTS:** Common contract; no direct-transform movement as simulation proof. Original asset-loader behavior remains a separate measured boundary; no wholesale Windows catalog transfer.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing LoadingSceneProbe, measured model/animation closure, one placeholder material family if needed.
- **TEST COMMAND:** Existing attributed prefab staging/build/device lifecycle, extended with a visible-pose assertion. Preflight and forced build; preserve prior receipts.
- **PASS CONDITION:** Device capture shows recognizable recovered Commando and a measured pose/animation change consistent with bone evidence, without activating startup/character simulation. Review remaining L4 gates explicitly.
- **FAILURE EVIDENCE TO CAPTURE:** First mesh/bind-pose/controller/material failure, sampled clip/time/bone transforms and matching capture.
- **STATE/JOURNAL UPDATES REQUIRED:** Record bounded visual acceptance; replan before L5; retain runtime/prefab rollback.
- **DEPENDENCIES:** L4c/J26.


## L5a — Original asset-loading and startup boundary audit
- **ID:** L5a
- **TITLE:** Select the first truthful startup integration experiment
- **CONTEXT:** L4 content passes with diagnostic bindings; original startup remains inactive.
- **OBSERVATION:** Original skin content is deferred through AssetReference GUIDs; the current probe supplies six measured assets explicitly.
- **HYPOTHESIS:** A bounded local provider can satisfy measured content requests without platform initialization or altering original gameplay methods.
- **TASK:** Consult R2Wiki memory-update/skin/content guidance, RoR2EditorKit AddressablesPathDictionary/cache, R2API Addressables/content implementation, RoR2ImportExtensions/ThunderKit catalog import, and Starstorm2/MSU or RoRSkinBuilder real skin/content use before inventing a provider. Trace exact current-input requests, release/failure semantics, startup ordering, mandatory entitlement/native services and Android-only profile paths. Read the ranked experiment in community-prior-art.md.
- **CONSTRAINTS:** Common contract; original installation/profile untouched, no fabricated service success, no broad catalog transfer or speculative middleware rewrite.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Local recovered-source reports under work/, concise authored boundary analysis; thin provider probe only after measured contract.
- **TEST COMMAND:** Read existing local recovered code and catalog evidence; use existing ./dev preflight/build/scene-run lifecycle when a device test is justified.
- **PASS CONDITION:** Exact next original method/request, expected result, content identity, startup prerequisites and profile boundary recorded. Audit alone does not pass L5.
- **FAILURE EVIDENCE TO CAPTURE:** First unresolved API/native/ownership contract, source location, typed key, lifecycle and failure propagation.
- **STATE/JOURNAL UPDATES REQUIRED:** Record L4 replan and L5 first hypothesis; retain L3/runtime and L4 content checkpoints.
- **DEPENDENCIES:** L4d. T03/T04/T08/T10 remain conditional.

- **RESEARCH STATUS:** Audit complete; candidate A controller lifecycle passes in J33. Architecture and full capability gates unchanged.
- **CANDIDATE A (FIRST):** Small owned initialization/catalog recipe plus typed location using original AssetBundleProvider/BundledAssetProvider. Exercise original AssetOrDirectReference<RuntimeAnimatorController>.LoadAsync for GUID 48ef8327759dd43439416d4823124d9c, correct controller/35 clips, shared handles, Reset/delayed release/reload and missing/wrong-type controls. Original startup remains inactive; explicitly diagnose/tick original manager cleanup for this bounded probe. Locator registration alone does not complete Addressables initialization.
- **CANDIDATE B:** Same original caller with a narrow custom provider only if the built-in provider has a measured Android limitation. Wider Android catalog rebuilding is later, on measured content demand.
- **EXIT DISCIPLINE:** Existing pass condition above is unchanged. The research recommendation is EXPERIMENTAL and audit alone does not pass L5. Provider failure ordering and all required evidence are specified in community-prior-art.md.

## L5a-1 — Original controller request with existing providers
- **ID:** L5a-1
- **STATUS:** PASS — J33, 50.17-second device survival; no startup/simulation claim
- **TITLE:** Exercise original deferred controller load/shared ownership/release
- **CONTEXT:** L5a research recommends existing providers before a custom replacement.
- **OBSERVATION:** Original runtime libraries implement bundle providers and the game wrapper/manager; initialization autoreleases its handle and cleanup depends on an inactive application event.
- **HYPOTHESIS:** A valid local initialization catalog plus one typed Android location can serve the unchanged wrapper and preserve shared ownership, failure and release behavior.
- **TASK:** Initialize a real zero-entry bootstrap catalog, register the measured controller location with original bundle providers, request through AssetOrDirectReference twice, reset/release/reload and test invalid requests. Use explicit diagnostic calls to original cleanup Update; no fake initialized flags.
- **CONSTRAINTS:** Common contract; unchanged original DLLs, startup/profile/body inactive, existing owned package and storage guards; provider exclusively owns the prefab bundle. Diagnostic ticking does not prove the game loop.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Authored ControllerAddressProbe, thin existing scene runner additions, ignored restored content stage and receipts.
- **TEST COMMAND:** ./dev prototype --action controller-prepare; ./dev build --target vulkan --force; ./dev prototype --action controller-run; ./dev test.
- **PASS CONDITION:** Current-PID initialized state, correct controller/35 clips, shared/retained/released/reloaded handles and bundle, failed missing-key/wrong-type controls, 50-second survival, no unexpected startup/native failure and owned cleanup.
- **FAILURE EVIDENCE TO CAPTURE:** First phase/status/exception, local catalog/settings, source and APK/payload hashes, logcat/crash/capture and cleanup.
- **STATE/JOURNAL UPDATES REQUIRED:** Classify first failure; update L5a status without passing L5; retain L3/L4 checkpoints.
- **DEPENDENCIES:** L5a prior-art audit; exact accepted J26 content recipe and current pinned runtime libraries.


## L5a-2 — Original avatar request and subobject identity
- **ID:** L5a-2
- **STATUS:** PASS — J34, valid original typed avatar request and 51.13-second device lifecycle
- **TITLE:** Resolve the original Commando avatar through the proven loader
- **CONTEXT:** L5a-1 controller lifecycle passes; FBX subobjects remain a distinct boundary.
- **OBSERVATION:** J26 explicitly bound an exported avatar, while J25 catalog reports describe its original typed subobject location. EditorKit subasset heuristics require current-input validation.
- **HYPOTHESIS:** The existing providers can resolve the measured Avatar subobject without a custom loader or full catalog transfer.
- **TASK:** Compare the pinned catalog key/type/subobject identity with actual exported bundle asset/subasset names. Extend only the accepted probe's typed location/request to the original avatar wrapper. Verify identity, validity and release/reload. Keep skin baking a separate subsequent task.
- **CONSTRAINTS:** Common contract; original application/body/profile inactive, unchanged original DLLs, diagnostic cleanup identified; no speculative FBX renaming or provider replacement.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Narrow authored probe, ignored typed mapping/accepted content stage and evidence; existing provider orchestration.
- **TEST COMMAND:** Existing catalog-addresses inspection as needed, forced Vulkan build and controller-run lifecycle; name any new thin action with this experiment.
- **PASS CONDITION:** Current-PID successful original typed avatar request with independently matched subobject identity, valid avatar and balanced ownership/reload; at least 50 seconds alive and owned cleanup.
- **FAILURE EVIDENCE TO CAPTURE:** Typed catalog and bundle names, first key/type/subobject/provider error, original wrapper results, source/APK/payload hashes and device evidence.
- **STATE/JOURNAL UPDATES REQUIRED:** Preserve failed candidates; record bounded result without passing full skin loading or L5. Keep accepted controller rollback.
- **DEPENDENCIES:** L5a-1/J33 and measured J25/J26 avatar identity; review community-prior-art.md before the subobject choice.


## L5a-3 — Original skin parameters and baking
- **ID:** L5a-3
- **STATUS:** PASS — J36, original baking/template identities/parameter release on Android; 70.92 seconds
- **TITLE:** Resolve default SkinDefParams and run original BakeAsync
- **CONTEXT:** Original controller and avatar deferred request lifecycles pass, with startup inactive.
- **OBSERVATION:** Original SkinDef.BakeAsync resolves deferred parameters and produces renderer/activation/mesh templates. Existing static content proof manually supplied defaults.
- **HYPOTHESIS:** Measured default-skin parameter and prefab references can support original template generation through the accepted provider path.
- **TASK:** Consult the pinned skin/community sources and current original implementation; measure the exact default SkinDef/params closure and expected template counts/identities before staging. Exercise parameter loading and original BakeAsync, stopping at the first unresolved dependency. Split skin application/material/mesh loading into later work if it adds a new boundary.
- **CONSTRAINTS:** Common contract; no original body/application/profile activation, no synthetic templates or rewritten game logic, unchanged original DLLs. Preserve diagnostic versus real game-loop scheduling distinction.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Narrow skin probe and measured local location/content recipe, ignored original-source/identity reports and device receipts.
- **TEST COMMAND:** Existing preflight, forced Vulkan build and guarded device lifecycle; add a thin skin-specific action only with this probe.
- **PASS CONDITION:** Original parameter identity and BakeAsync completion, independently expected template counts/references, released temporary parameter ownership, stable device lifetime and owned cleanup. No full skin application or gameplay claim.
- **FAILURE EVIDENCE TO CAPTURE:** First unresolved key/reference/static initializer, nested coroutine exception, template/result identity, source/APK/payload hashes and current-PID device evidence.
- **STATE/JOURNAL UPDATES REQUIRED:** Record outcome and any split task, preserve failed attempts and controller/avatar rollback; L5 remains open.
- **DEPENDENCIES:** L5a-2/J34, measured default skin/params and existing prior-art audit.


## L5a-4 — Original skin application to the inactive model
- **ID:** L5a-4
- **STATUS:** PASS — J38, original mesh assignments and material records on inactive model; 70.87 seconds
- **TITLE:** Load and apply the baked default material/mesh references
- **CONTEXT:** Original controller/avatar loading and default skin baking pass separately.
- **OBSERVATION:** Baked templates retain deferred material and mesh references; baking alone does not assign renderers or load those assets.
- **HYPOTHESIS:** Measured material and three mesh subobject mappings let original RuntimeSkin.ApplyAsync populate the inactive recovered model correctly.
- **TASK:** Inspect pinned skin/community implementations and current original ApplyAsync; measure exact deferred keys/provider mappings and resulting renderer assignments. Apply using the original method on an inactive model, assert mesh/material identities and reference counts, then release. Split at the first new loading/assignment boundary before adding activation or visuals.
- **CONSTRAINTS:** Common contract; original DLLs unchanged, no CharacterBody/application/profile activation, no diagnostic assignment substituted for original skin application. Diagnostic rendering can follow but does not imply gameplay or shader parity.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Narrow existing probe extension, measured local material/mesh locations, ignored restored skin stage and evidence.
- **TEST COMMAND:** Existing preflight, forced Vulkan build and owned device lifecycle; add only the skin-application preparation needed for this task.
- **PASS CONDITION:** Original ApplyAsync completes; expected mesh components and CharacterModel material records receive the correct recovered identities; ownership/release assertions and stable device lifetime pass. No missing required references or new unexplained exceptions.
- **FAILURE EVIDENCE TO CAPTURE:** First typed key/provider/subobject/assignment failure, original coroutine results, current renderer identities and reference ownership, APK/payload hashes and device evidence.
- **STATE/JOURNAL UPDATES REQUIRED:** Preserve failed attempts, update bounded skin status without passing startup/simulation, retain J36 rollback.
- **DEPENDENCIES:** L5a-3/J36 and current-input material/mesh identity mappings; shared controller/avatar providers stay accepted.


## L5b-1 — First lawful startup segment and Android profile foundation
- **ID:** L5b-1
- **STATUS:** PASS — J39, first-yield/PreFrame and independent filesystem candidate; full startup remains open
- **TITLE:** Cross from isolated content into measured original startup
- **CONTEXT:** J33–J38 prove bounded original asset loading, baking and inactive model application. Original startup/menu and L5.5 simulation remain unexecuted.
- **OBSERVATION:** Static InitializeGameRoutine trace reaches Wwise, Addressables, a filesystem rooted at Application.dataPath, PlatformSystems.Init and a Steam-client delegate before profile loading. This order and native/service obligations need explicit device-relevant boundaries.
- **HYPOTHESIS:** An isolated first startup segment and separate Android-owned profile/content roots can expose the next real blocker without activating several unmeasured services at once.
- **TASK:** Reuse community-prior-art.md startup/profile findings; revalidate actual pinned assembly signatures/call order and mandatory checks. Select and record the smallest executable original startup segment, its stop boundary and truthful unavailable capabilities. Establish and test a fresh Android-only filesystem root before enabling profile writes. Implement only the necessary input-gated adapter/observation, then execute the selected segment on device; stop at its first failure.
- **CONSTRAINTS:** Common contract; no fabricated ownership/authentication/service success, no host Steam profile access or changes, no broad startup patching, no native middleware replacement without measured need. Wwise no-audio handling requires a valid lifecycle, not silent success.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Narrow startup/path audit and probe, minimal profile/content path adapter if justified, ignored evidence and checkpoint receipts.
- **TEST COMMAND:** Existing doctor/preflight/forced build/owned device lifecycle; add only a thin startup-segment action with its exact assertions.
- **PASS CONDITION:** Fresh Android profile path isolation verified; the selected original segment reaches its declared boundary with attributable events, correct capability states and stable device lifetime. A discriminating failure completes the experiment but does not pass L5.
- **FAILURE EVIDENCE TO CAPTURE:** First initialization/native/path/entitlement failure, concrete call/signature and capabilities, profile backing/isolation evidence, source/APK/payload identities and device capture.
- **STATE/JOURNAL UPDATES REQUIRED:** Record first blocker or passed segment; preserve J38 asset rollback and separate L5 startup from L5.5 simulation. Keep renderer material update unproven until exercised.
- **DEPENDENCIES:** L5a-4/J38; earlier startup/profile prior-art audit. Revisit audio access/platform requirements only where this segment needs them.

## L5b-2 — Original startup loading-scene handoff
- **ID:** L5b-2
- **STATUS:** PASS — J40, real loadingbasic/Canvas and two original frame yields; no component activation
- **TITLE:** Connect the proven first startup phase to recovered loadingbasic
- **CONTEXT:** J39 proves original PreFrame and an isolated Android filesystem candidate; L4 proves recovered loading scene content independently.
- **OBSERVATION:** The next original routine segment redirects console output, subscribes scene events, waits for loadingbasic, accesses LoadingScreenCanvas.Instance.percentage and yields two frames before enabling components.
- **HYPOTHESIS:** The recovered loading scene and persistent UI can satisfy these original startup references without prematurely activating audio/platform components.
- **TASK:** Inspect the exact recovered application/UI component identities and next coroutine yield boundaries. Restore J39, load the accepted recovered scene with application startup still controlled, resume only through the measured loading-UI frame yields, and stop before EnableBehaviours. Verify original loading scene/Canvas linkage and capture the first missing lifecycle/reference requirement. Audit the serialized enable list before any later activation.
- **CONSTRAINTS:** Common contract; no duplicate automatic application Awake or full startup, no fabricated scene readiness or service success, no profile-global reassignment. Do not skip a failing original reference by replacing it with a dummy. Preserve the J39 path and known-good content.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing narrow startup probe and preparation, recovered scene/component evidence under ignored work/, state and journal.
- **TEST COMMAND:** Existing startup preparation/run lifecycle with an explicit next-segment configuration; preflight, forced Vulkan build, current-attempt device report and screenshot.
- **PASS CONDITION:** Original routine recognizes actual recovered loadingbasic and real loading UI, reaches the declared yield stop before component enabling, with stable device lifetime and no new unexplained errors. This remains a segment proof, not L5 menu acceptance.
- **FAILURE EVIDENCE TO CAPTURE:** First scene/singleton/component/reference failure, original yield position, current-PID exception/capture, preserved source/APK/payload identities.
- **STATE/JOURNAL UPDATES REQUIRED:** Record the exact reached boundary, retain J39 rollback, then select the measured component/audio boundary. Keep L5/L9/L5.5 open.
- **DEPENDENCIES:** L5b-1/J39 and accepted L4 recovered scene evidence.

## L5b-3 — Recovered application host and startup component lifecycle
- **ID:** L5b-3
- **STATUS:** NEXT
- **TITLE:** Measure the six startup components before crossing into audio
- **CONTEXT:** J40 proves loading-scene/UI handoff with the routine on an inactive diagnostic host.
- **OBSERVATION:** The recovered application's enable list has GlobalShaderTextures, two PostProcessVolume entries, InterpolationController, NGSS_Local and FPSQueue, all disabled/inactive. The diagnostic host's empty list cannot establish their lifecycle.
- **HYPOTHESIS:** Their measured initialization requirements can be isolated while retaining real serialized references and preventing automatic full application startup.
- **TASK:** Inspect original Awake/OnEnable/Start/update paths and native/shader requirements of these six components plus application Awake. Select the smallest real-host/component experiment, preserve references, and explicitly record inactive enable flags versus executed lifecycle. Stop before Wwise and split at the first component failure. Reuse prior-art audit where applicable.
- **CONSTRAINTS:** Common contract; no automatic full startup, empty-list success, speculative graphics rewrites, fake audio/services or saves. Keep user's owned app installed; update in place.
- **EXPECTED FILES/SYSTEMS TO TOUCH:** Existing narrow startup probe/preparation, ignored component metadata/serialized-contract reports, only a measured lifecycle adapter if needed.
- **TEST COMMAND:** Existing startup preparation, preflight, forced Vulkan build and current-attempt/PID device assertions; use a thin component action only if required.
- **PASS CONDITION:** Selected real component lifecycle and serialized references execute with correct assertions and stable device lifetime; report exactly which components ran. No L5 menu pass from toggled flags on inactive objects.
- **FAILURE EVIDENCE TO CAPTURE:** First component initialization/reference/shader/native failure, enabled/active states, actual lifecycle events, original method and source/APK/payload identities.
- **STATE/JOURNAL UPDATES REQUIRED:** Preserve J40 rollback; select next component or Wwise boundary from evidence. Keep actual saves/menu/simulation open.
- **DEPENDENCIES:** L5b-2/J40 and measured original component/application lifecycle audit.
