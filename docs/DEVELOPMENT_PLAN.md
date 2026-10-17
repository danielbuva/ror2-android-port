# Development plan — prove more RoR2 before expanding the laboratory

**Current execution mode (user direction, 2026-10-04): whole-game integration.** Assemble as much coherent offline gameplay as possible before verification; use temporary Android adapters with truthful unavailable capabilities and preserve legal/platform boundaries. Build/run the integrated game on Nova and iterate its first failures. This supersedes the prior preference for isolated subsystem proofs, while retaining exact inputs/toolchain, provenance, storage safety, rollback and truthful capability reporting. Existing gates describe evidence; they are not a requirement to serialize every feature into a new micro-probe.

Approved direction: Architecture C in ADR-001: exact-editor Android IL2CPP player, selective managed preservation, locally converted content and explicit platform adapters. Controlled C#9 reconstruction is the bounded fallback. This roadmap is the canonical execution policy; current results belong in PORTING_STATE.md and milestones.md.

**Current independent-work direction (2026-10-07):** Keep all Moon/finale and integrated rollback artifacts intact. Prioritize broad independent original content/director coverage, offline menus/sessions, persistence, controller generalization, stability and incremental packaging. Batch independent host-validated changes into one composed Android candidate. Same-package APK updates are explicitly authorized; keep one owned app. Skip paths requiring manual navigation or user handoff, including unattended Moon/finale/escape routing. Rendering proceeds only through concrete original-data/binary paths; exact appearance/runtime ambiguities are deferred to a later PC differential pass. Track original/recovered/adapted/approximate fallback/unavailable in [subsystem coverage](subsystem-coverage.md). Sleep the OLED whenever idle.

**Verification budget (latest user direction):** Accumulate larger independent content/application changes using cheap local contract, import and compiler checks. Reserve expensive full-route verification for meaningful composed milestones or an actual regression. Do not repeat an unchanged death/restart or four-stage slice for each content addition. Repeated sessions remain justified when a lifecycle change or new observation can resolve the confirmed completed-session retention; state that specific question and keep the resulting measurement distinct from gameplay acceptance. Preserve first-failure evidence and investigate new failures without reducing the breadth priority.

**Visual authority:** Reproduce the original PC build's authored appearance, including lighting, color, fog, outlines, material response, particles and gameplay readability. Prefer matching PC captures of the same stage/object/character and measured original scene/material data. A brighter or more polished Android image is not evidence of fidelity. Mark replacements as approximations, record unsupported features and keep parity open until comparative evidence supports it. Do not invent grading, atmosphere or lighting to hide missing source behavior. See [visual restoration](visual-restoration.md) for current comparisons and limits.

## Scientific contract

Observation → hypothesis → smallest experiment → preflight → build/run → evidence → first-failure classification → state update → logical commit.

Before adding tooling, name the immediate experiment and concrete failure it prevents. Extend ./dev and the current harness; prefer an experiment-specific probe. Use forced builds for uncertain scene cache identity. Serialize editor mutations and wait for real completion; dispatch is not success. Keep early device probes in the existing lab package; the reconstruction APK stays host-only until supported safely. Add only the observation needed for the next subsystem. Test storage scale immediately before large payloads.

Original installation is immutable. Proprietary binaries/assets/source, generated projects, middleware, raw logs and screenshots stay ignored under work/. Do not fabricate ownership, entitlement, authentication or service success. Keep the approved exact editor in environment/toolchain.json and its bundled toolchain (2021.3.45f2 for Steam build25475991; retain33f1 for old rollbacks), pinned MCP and canonical authorized-device adb workflow. Preserve local server/client/authority semantics while remote services are deferred.

Record results once, in the journal, and replace `PORTING_STATE.md` rather than appending to it; the documentation rules and definition of done are in `AGENTS.md`. Review staged files and commit coherent changes. Split tasks that expand. A failed discriminating experiment can complete an issue without passing its milestone.

## Ordered gates

L0–L2 baseline → L3 original managed execution → L4 first recovered scene → L5 lawful startup/menu → L5.5 original character simulation → L6 complete controllable stage → L7 combat/complete stage → L8 complete offline victory.

Supporting gates: L9 profile foundation before L5 and persistence alongside L8; L10 audio feasibility early and real audio when access/runtime permits; L11 minimum graphics with L4/L6/L7 and parity later; T10 before multi-GiB content. L12 sustained performance and L13 clean transformation follow a meaningful/stable run. See milestones.md for each objective, dependencies and acceptance.

L4 audits required GUIDs, local fileIDs, scripts, subassets and catalogs; loadingbasic and a dependency-rich animated prefab must work on device. A scene container or editor hierarchy alone does not pass. L5 traces actual initialization; optional no-audio handling must cover observed lifecycle, callbacks and teardown, not report a fake initialized engine. Mandatory entitlement remains an independent gate. L6 introduces a complete original stage to the already proven character. L7 isolates enemy/damage, pickups/interactables, director and teleporter before normal stage completion. L8 requires normal victory/results, profile persistence and a second run before marking stable; no forced completion.

## Acceptance defaults

Native ARM64 Android 13 on the authorized QCS8550/Adreno 740 handheld; no x86 execution layer. First complete run: Commando/default abilities, easiest normal difficulty, one base-game victory route, fresh Android-only profile. Built-in controller first. Use passing Vulkan/device driver; MrPurple T30 is a separate measured integration unless evidence makes it necessary.

Nonessential decorative effects may remain placeholders. Navigation, player/enemy silhouettes, damage projectiles, hazards, health and objectives must be readable by L7. Audio can remain explicitly unavailable. Measure load time, APK/data size, transfer/install time, frame time and memory at capability gates; optimize measured bottlenecks after meaningful gameplay. Stable 30 FPS first, 60 FPS later. Never treat capped harness FPS or unavailable GPU timings as game performance.

## Storage, rollback and evidence

Small APK plus separately synced large Android data. Query live adopted UUID, physical/adopted capacity every install; preserve installation scratch guards. Verify package placement and actual runtime data backing. Hash changed files; stage complete dependent generations before activation once multi-file updates require it. Resume initially skips verified files and retries the interrupted file. Before multi-GiB data, T10 measures interruption/retry, unchanged sync, update retention and owned cleanup with realistic synthetic data.

Retain previous APK, compatible payload, host sources and profile backups before intentional receipted reset. Never format/repartition/change storage configuration or delete/move unrelated data. Account for old/new payloads and temporary space. Record APK/payload identities separately using existing receipts until richer enforcement is needed.

Local checkpoint pointers: LAST_KNOWN_GOOD_RUNTIME, SCENE, SIMULATION, PLAYABLE, RUN under work/checkpoints. Bind commit, accepted input, toolchain, transformations, APK hash, payload manifest, configuration and passing evidence. Failures never advance pointers. Each attempt has immutable logs/results, relevant state and visually reviewed capture. Restricted native crash access is recorded honestly.

## Architecture review

Review ADR-001 if required original code cannot AOT without pervasive rewriting, type identity cannot be retained, essential content cannot be reconstructed, or required middleware/platform access has no legitimate bounded alternative. J61 meets the last condition. J62 review retains C as platform-deferred and selects only L10-a, a read-only audit of remaining no-audio lifecycle obligations; Astra reviews its evidence before authorizing a runtime candidate. A controlled C#9 trial is appropriate only when it tests an independent architecture question against the same bounded assertions; it cannot solve missing lawful platform access, ownership, authentication, entitlement, licensing or unavailable middleware. Eleven initial compiler errors are not a total-work estimate. After two supported candidates fail at a boundary, reassess the hypothesis before another version. Reconstruction does not solve licensing/entitlement/absent authoring/storage.

Replan at L3, L4, L5.5, L6, L7 and L8. Authentication, licensing, OS permission, physical device action or an evidence-dependent material architecture choice can require user input; ordinary bounded development continues autonomously.

## Postponed

Moon/finale acceptance resumes when manual input is available; final normal full-route verification remains required. Additional survivors/DLC/routes, existing Steam-profile import/cloud, remote multiplayer/platform services, 60 FPS, end-user storage import and release packaging/signing/distribution remain later gates. The latest independent-work direction brings visual parity, broader base content, offline application flow, controller breadth and performance measurement forward; real audio still requires authorized compatible access. See risk-register.md for early detection/fallbacks.
