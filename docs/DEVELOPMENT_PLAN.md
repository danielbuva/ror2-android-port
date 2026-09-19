# Development plan — prove more RoR2 before expanding the laboratory

Approved direction: Architecture C in ADR-001: exact-editor Android IL2CPP player, selective managed preservation, locally converted content and explicit platform adapters. Controlled C#9 reconstruction is the bounded fallback. This roadmap is the canonical execution policy; current results belong in PORTING_STATE.md and milestones.md.

## Immediate execution

T01 → T02 → T05 → T06 → T07. T03/T04/T08/T10 are conditional support, not wholesale prerequisites. T01 is non-negotiable: `./dev doctor`, `./dev preflight`, `./dev test`, `./dev smoke --target vulkan`. Stop at the first failed prerequisite. Unknown input requires inventory/diff review and explicit local acceptance. Do not repeat unchanged failed Rewired builds or reconstructed Play Mode.

T01 passed anew at work/runs/20260913T020341.114229Z-46130c90d7a1; screenshot visually verified and disposable package removed. Historical G2 remains utility execution/static geometry, not gameplay.

## Scientific contract

Observation → hypothesis → smallest experiment → preflight → build/run → evidence → first-failure classification → state update → logical commit.

Before adding tooling, name the immediate experiment and concrete failure it prevents. Extend ./dev and the current harness; prefer an experiment-specific probe. Use forced builds for uncertain scene cache identity. Serialize editor mutations and wait for real completion; dispatch is not success. Keep early device probes in the existing lab package; the reconstruction APK stays host-only until supported safely. Add only the observation needed for the next subsystem. Test storage scale immediately before large payloads.

Original installation is immutable. Proprietary binaries/assets/source, generated projects, middleware, raw logs and screenshots stay ignored under work/. Do not fabricate ownership, entitlement, authentication or service success. Keep Unity 2021.3.33f1 and its bundled toolchain, pinned MCP and canonical authorized-device adb workflow. Preserve local server/client/authority semantics while remote services are deferred.

Each issue uses the full schema in execution-backlog.md. Preserve attempt evidence, update concise PORTING_STATE.md after meaningful progress, append failures and revisit conditions to PORTING_JOURNAL.md, update milestones/backlog at gates, review staged files and commit coherent changes. Split tasks that expand. A failed discriminating experiment can complete an issue without passing its milestone.

## Ordered gates

L0–L2 baseline → L3 original managed execution → L4 first recovered scene → L5 lawful startup/menu → L5.5 original character simulation → L6 complete controllable stage → L7 combat/complete stage → L8 complete offline victory.

Supporting gates: L9 profile foundation before L5 and persistence alongside L8; L10 audio feasibility early and real audio when access/runtime permits; L11 minimum graphics with L4/L6/L7 and parity later; T10 before multi-GiB content. L12 sustained performance and L13 clean transformation follow a meaningful/stable run. See milestones.md for each objective, dependencies and acceptance.

L4 audits required GUIDs, local fileIDs, scripts, subassets and catalogs; loadingbasic and a dependency-rich animated prefab must work on device. A scene container or editor hierarchy alone does not pass. L5 traces actual initialization; optional no-audio handling must cover observed lifecycle, callbacks and teardown, not report a fake initialized engine. Mandatory entitlement remains an independent gate. L6 introduces a complete original stage to the already proven character. L7 isolates enemy/damage, pickups/interactables, director and teleporter before normal stage completion. L8 requires normal victory/results, profile persistence and a second run before marking stable; no forced completion.

## L5.5 — original character simulation

Prerequisite: L5. Use the smallest functioning recovered environment and original Commando prefab dependency closure. A diagnostic camera, simple collision surface, neutral lighting and replacement materials are allowed. Do not require a whole stage/director/full camera rig.

Issue 1: spawn an original CharacterMaster/CharacterBody without input; assert linkage, components, local authority and stable original state-machine ticking.
Issue 2: feed a recorded short sequence at the game's input boundary; assert original movement/stop, jump/landing where supported and corresponding state transitions. Never move the Transform directly to claim simulation success.
Issue 3: inspect built-in handheld controls and bind them to the same proven boundary; verify manual movement and a state-changing action. Scripted input is not controller acceptance.

Record master/body identity, authority, state, velocity/position, grounding and exceptions. Use existing build/install/run/capture; add a thin ./dev prototype --action character-simulation only when needed. Pass: three cold launches with ≥60 seconds stable simulation each, deterministic assertions, manual built-in input, structured and visual evidence, no unexplained required-component/authority failure.

Failure order: prefab/reference → creation → authority → state initialization/tick → physics/movement → input. Roll back to L5 APK and payload. Sync only this closure after live storage checks. Complete stage, enemies, combat, full camera/audio/material parity are non-goals. Establish LAST_KNOWN_GOOD_SIMULATION and replan before L6.

## Acceptance defaults

Native ARM64 Android 13 on the authorized QCS8550/Adreno 740 handheld; no x86 execution layer. First complete run: Commando/default abilities, easiest normal difficulty, one base-game victory route, fresh Android-only profile. Built-in controller first. Use passing Vulkan/device driver; MrPurple T30 is a separate measured integration unless evidence makes it necessary.

Nonessential decorative effects may remain placeholders. Navigation, player/enemy silhouettes, damage projectiles, hazards, health and objectives must be readable by L7. Audio can remain explicitly unavailable. Measure load time, APK/data size, transfer/install time, frame time and memory at capability gates; optimize measured bottlenecks after meaningful gameplay. Stable 30 FPS first, 60 FPS later. Never treat capped harness FPS or unavailable GPU timings as game performance.

## Storage, rollback and evidence

Small APK plus separately synced large Android data. Query live adopted UUID, physical/adopted capacity every install; preserve installation scratch guards. Verify package placement and actual runtime data backing. Hash changed files; stage complete dependent generations before activation once multi-file updates require it. Resume initially skips verified files and retries the interrupted file. Before multi-GiB data, T10 measures interruption/retry, unchanged sync, update retention and owned cleanup with realistic synthetic data.

Retain previous APK, compatible payload, host sources and profile backups before intentional receipted reset. Never format/repartition/change storage configuration or delete/move unrelated data. Account for old/new payloads and temporary space. Record APK/payload identities separately using existing receipts until richer enforcement is needed.

Local checkpoint pointers: LAST_KNOWN_GOOD_RUNTIME, SCENE, SIMULATION, PLAYABLE, RUN under work/checkpoints. Bind commit, accepted input, toolchain, transformations, APK hash, payload manifest, configuration and passing evidence. Failures never advance pointers. Each attempt has immutable logs/results, relevant state and visually reviewed capture. Restricted native crash access is recorded honestly.

## Architecture review

Review ADR-001 if required original code cannot AOT without pervasive rewriting, type identity cannot be retained, essential content cannot be reconstructed, or required middleware/platform access has no legitimate bounded alternative. J61 meets the last condition and requires review before another game experiment. A controlled C#9 trial is appropriate only when it tests an independent architecture question against the same bounded assertions; it cannot solve missing lawful platform access, ownership, authentication, entitlement, licensing or unavailable middleware. Eleven initial compiler errors are not a total-work estimate. After two supported candidates fail at a boundary, reassess the hypothesis before another version. Reconstruction does not solve licensing/entitlement/absent authoring/storage.

Replan at L3, L4, L5.5, L6, L7 and L8. Authentication, licensing, OS permission, physical device action or an evidence-dependent material architecture choice can require user input; ordinary bounded development continues autonomously.

## Postponed

Full audio/graphics parity, additional survivors/DLC/routes, existing Steam-profile import/cloud, remote multiplayer/platform services, broad devices, 60 FPS, end-user storage import, release packaging/signing/distribution. Investigate earlier only when a measured dependency requires it. See risk-register.md for early detection/fallbacks.
