# Public alpha checklist

Re-audited 2026-11-11 against merged evidence since
[audit #338](https://github.com/danielbuva/ror2-android-port/pull/338), including
journal J1380–J1405 and changes through
[PR #431](https://github.com/danielbuva/ror2-android-port/pull/431).
All 18 acceptance gates remain open; linked results establish partial progress.
Remaining actions are listed in the [execution backlog](execution-backlog.md).

The user accepts [owner-built Route A](ADR-002-public-alpha-distribution.md);
[ADR-001](ADR-001-port-architecture.md) retains Architecture C, native IL2CPP ARM64
and the current renderer. Phone-only owner builds are the installation target;
retain the desktop fallback. The [stage assessment](phone-owner-build.md) precedes
build-pipeline changes. This checklist makes no alpha-readiness claim.

## Decision and reproducibility

- [ ] Produce a fully playable source-derived APK from the user's original game
      files, preserving Architecture C and the latest lab build's behaviour,
      content, visuals, performance and features (current reference `9f904392`,
      source `6c12b506`). Require strict PPtr/file-ID, type-tree, script-binding,
      collider and other gameplay-critical checks, loadability and in-game
      verification. Byte equality is diagnostic; historical 693/705 availability
      and 685 raw-exact results do not establish playability.
      Then qualify the complete phone-only import → convert → install → play →
      newer port-release update flow, preserving profiles/settings and rebuilding
      only changed outputs where possible, including Check for updates.
      Discovering newer Steam inputs is secondary; report unknown/changed assets
      clearly. See the [converter contract](accepted-build-reconstruction.md).
      [J1388](PORTING_JOURNAL.md#j1388--emit-and-typed-load-a-closed-source-native-bundle-subset)
      typed-loads a partial native bundle;
      [#428](https://github.com/danielbuva/ror2-android-port/pull/428)
      completes source camera-program suppliers. Complete graph/load, APK and
      device playability remain unqualified.
- [ ] Qualify permitted tool acquisition, Android app execution, complete game
      AOT/metadata construction, content/shader production, durable owner signing
      and user-mediated installation/update as one complete flow, including
      Check for updates. The [stage evidence](phone-owner-build.md) and
      [host-qualified installer integration](PORTING_JOURNAL.md#j1257--integrate-resumable-public-phone-installation-and-updates)
      do not establish complete game conversion or phone acceptance.
      [#408](https://github.com/danielbuva/ror2-android-port/pull/408)
      adds host-tested disposable-package assembly, without APK/device acceptance.
- [ ] Complete public-input bootstrap without private generated assets or
      workstation analysis receipts ([structural blockers](execution-backlog.md#structural-cleanup)).
      Reuse the [owner assembly prefix](OWNER_ASSEMBLIES.md); resolve remaining
      content/shader producers and [component distribution grants](phone-owner-build.md#tool-and-redistribution-boundaries).
- [ ] Qualify the complete owner-generated output on the selected alpha device,
      with committed source/input/toolchain receipts, ordinary installation/update
      and matched performance ([acceptance gates](phone-owner-build.md#proof-gates)).
      Preserve the original installation, Main's editor/build mutex/device and
      desktop fallback. IL2CPP alone does not prove equivalent performance.
      [J1401](PORTING_JOURNAL.md#j1401--load-typed-results-definitions-before-dependent-drop-tables)
      verifies bounded ordinary Start on a lab APK, not the converter's output.
- [ ] Complete the [ADR-002 findings review](ADR-002-public-alpha-distribution.md)
      before adopting a replacement pipeline or final installation architecture.
      Keep other gameplay backends excluded; audit public artifacts and keep
      owner-generated game content private.

## Packaging and acquisition

[ALPHA_POLICY.md](ALPHA_POLICY.md) owns local-file acquisition, separate alpha
identity, signing/update/rollback and cloud deferral. Its
[acceptance matrix](ALPHA_POLICY.md#final-flow-acceptance-contract) distinguishes
host contracts from installed-alpha acceptance.

- [ ] Phone-qualify alpha identity, issued-version/same-key updates and forward
      rollback, including real profile/settings backup, verified restore,
      interruption and cold-start retention.
      [J1258](PORTING_JOURNAL.md#j1258--integrate-owned-alpha-updates-rollback-and-profile-retention)
      qualifies synthetic host contracts only.
      [J1401](PORTING_JOURNAL.md#j1401--load-typed-results-definitions-before-dependent-drop-tables)
      retains profile/settings hashes across a lab update; the final alpha
      identity, owner signing, backup/restore and rollback flow remain unqualified.
- [ ] Phone-qualify folder/ZIP validation, cancellation and honest supported/unknown
      version refusal with legitimate input cohorts and actual SAF providers
      ([acceptance matrix](ALPHA_POLICY.md#final-flow-acceptance-contract)).
      Keep source installations read-only; account downloads and Steam Cloud deferred.

Laboratory capacity, placement and runtime-backing receipts in
[J1071](history/journal-J1-J1177/PORTING_JOURNAL.md#j1071--qualify-software-touch-native-pause-and-recovery)
retain J595/J755 ownership guards; final alpha installation remains separate.

## Controls, UI and sessions

- [ ] Qualify ordinary physical input, original/native mappings and rebinding
      against the [measured-input contract](INPUT_QUALIFICATION.md).
      [PR #239](https://github.com/danielbuva/ror2-android-port/pull/239)
      qualifies paused rebinding host contracts, with physical acceptance open.
- [ ] Qualify the physical touchscreen digitizer, acquired-equipment activation
      and genuine target interaction.
      [J1071](history/journal-J1-J1177/PORTING_JOURNAL.md#j1071--qualify-software-touch-native-pause-and-recovery)
      covers software touch and bounded native consumers; empty-slot/target
      requests are bank-only.
- [ ] Qualify ordinary hardware navigation and remaining [player screens](SCREEN_COVERAGE.md)
      against [subsystem coverage](subsystem-coverage.md), including complete
      source presentation.
      Source [Menu/HUD graph production](accepted-build-reconstruction.md)
      still requires current-code loadability, in-game presentation and hardware
      navigation checks; historical byte differences alone do not block acceptance.
- [ ] Qualify physical end-run/results navigation and repeated-session memory
      ([session owners](ARCHITECTURE.md#ownership)).
      [J1342](PORTING_JOURNAL.md#j1342--restore-original-point-sound-timeout-dispatch)
      drains the instrumented audio timeout queue;
      [J1350](PORTING_JOURNAL.md#j1350--restore-original-console-retention-default-at-composed-startup)
      retains positive matched-menu growth after twelve assisted sessions.
      [J1402](PORTING_JOURNAL.md#j1402--continue-memory-observations-through-native-loss-and-menu)
      verifies assisted loss → results → menu → ordinary Start continuation;
      the 32-session diagnostic stopped after ten completions on lost thermal
      telemetry. Subsequent [transport](PORTING_JOURNAL.md#j1403--preserve-session-process-transport-failures)
      and [cooldown](PORTING_JOURNAL.md#j1405--cool-supervised-memory-sessions-between-verified-endings)
      fixes support a completed 32-session supervised UI-abandon diagnostic
      ([J1407](PORTING_JOURNAL.md#j1407--preserve-cooldown-admission-readings-across-display-wake)).
      Final-16 matched-menu managed growth remains positive; physical navigation,
      a memory plateau and ordinary long-run dependency retention remain open.
      [J1408](PORTING_JOURNAL.md#j1408--reclaim-measured-returned-pool-storage-after-completed-sessions)
      clears measured returned BulletHit/Renderer-list storage after each of three
      supervised sessions, with continuation; positive matched-menu managed growth
      remains. This scoped cleanup does not close the memory or physical-input gate.
- [ ] Coordinate gameplay/audio/animation prerequisites with the main session;
      acceptance follows [capability gates](milestones.md), including an
      unassisted run. Keep Moon/finale manual.

## Performance (release gate)

Correctness comes first: no optimization may regress functional/structural
correctness, original behaviour or visual output to improve a benchmark. Byte
equality remains a diagnostic under the converter contract. Reconstruction-gap closure stays
the priority; these gates must pass before any public release.

- [ ] Profile the complete phone converter (import → reconstruction → APK → install)
      on supported hardware and record wall time, peak memory, peak/sustained
      temperature and peak/final storage per stage. Optimize the largest costs and
      set per-device budgets; installation time, memory, heat and storage use are
      minimized without changing any produced byte.
- [ ] Profile the installed game over sustained sessions on supported hardware and
      record sustained FPS, frame-time pacing (percentiles, hitches), battery drain
      and thermal behaviour, with visual fidelity checked against the original. Fix
      the largest regressions and set per-device budgets; no fidelity reduction
      without an explicit, documented user decision.

Game baseline and attribution plan: [retained sustained report](performance-game.md),
qualified as host-only in [J1359](PORTING_JOURNAL.md#j1359--retained-sustained-game-performance-report).
The 30-minute Main Nova observation averages 49.06 FPS; 1.537% of active frames
exceed 50 ms. Raw frame percentiles, battery drain and throttling onset remain
unmeasured. Periodic interval-mean percentiles cannot close the pacing gate.
[J1389](PORTING_JOURNAL.md#j1389--report-final-ten-minute-sustained-frame-counters)
adds retained final-ten-minute aggregate counters: 50.032 FPS and 1.274% of
frames above 50 ms. This is host analysis of assisted play, not a new run or
raw frame-percentile qualification.

The bounded 2026-11-12 assisted capture reconciles 4,693 individual frames and
reports true p50/p95/p99 of 16.67/16.92/49.94 ms; see the
[capture qualification](performance-game.md#bounded-raw-capture-qualification).
Its 80-second observation leaves sustained ordinary-play pacing, capture overhead,
battery drain and throttling onset open.

Startup [audio-verification reuse](PORTING_JOURNAL.md#j1386--reuse-install-bound-audio-verification-and-partition-loading-costs)
and [catalog discovery](PORTING_JOURNAL.md#j1390--reuse-typed-item-provider-discovery-during-ordinary-startup)
provide bounded device evidence; complete converter and sustained-game profiles
remain required.
Original audio callback attribution identifies bank results as the final startup
prerequisite in one bounded run; it preserves readiness and scheduling and does
not qualify a total-load speedup
([J1422](PORTING_JOURNAL.md#j1422--attribute-original-audio-readiness-callback-waits)).

Proposed game budgets (targets, not accepted results), at original visual fidelity:

| Device | Sustained workload | Proposed pacing budget | Energy/thermal budget |
| --- | --- | --- | --- |
| Main Nova, 120 Hz panel | 30 minutes of representative ordinary play, each supported stage | Mean >=60 FPS; raw frame p50 <=16.67 ms, p95 <=33.334 ms, p99 <=50 ms; >50 ms frames <=1% | Establish unplugged energy baseline; propose <=10 battery percentage points per 30 minutes, pending measurement. Record temperature/exposure and clock limits; heat alone is not failure. |
| Ayn Thor, top panel only | Same workload, native display mode recorded | Start with the same 60 FPS/pacing targets; no retained comparable game trace, so qualification stays open | Measure drain and thermal exposure independently; do not transfer Nova results. |

Other hardware needs its own measured baseline before support. For every device,
report both whole-session and final ten-minute pacing, plus hitch counts and
throttling evidence. Keep the existing admission, safety-stop and one-second
thermal sampling policy; proposed performance budgets do not change those limits.

## Stability and playtests

- [ ] Attribute and bound repeated-session managed growth, then qualify a long
      device series ([open evidence](execution-backlog.md#stability-and-performance)).
      [J1327](PORTING_JOURNAL.md#j1327--release-destroyed-overlap-discovery-targets-after-session-teardown)
      removes destroyed overlap targets;
      [J1350](PORTING_JOURNAL.md#j1350--restore-original-console-retention-default-at-composed-startup)
      still shows positive twelve-session growth.
      [J1353](PORTING_JOURNAL.md#j1353--capture-the-requested-final-menu-heap)
      supplies endpoint heaps for attribution, without establishing a plateau.
      [J1402](PORTING_JOURNAL.md#j1402--continue-memory-observations-through-native-loss-and-menu)
      extends assisted observations through native loss; the interrupted series
      does not establish completion or a plateau.
- [ ] Complete real interrupted-write/ENOSPC and sustained performance/thermal
      cases on supported hardware.
      [J1311](PORTING_JOURNAL.md#j1311--recover-native-settings-after-writer-termination-and-activity-restart)
      qualifies writer termination, native recovery/resave and protected-file
      retention; power-cut and filled-filesystem cases remain open.
      Apply the current [thermal policy](PLAYTESTING.md#stability-persistence-and-updates),
      including [J1356](PORTING_JOURNAL.md#j1356--honor-thermal-admission-exclusions-above-80-c).
      Host policy checks and assisted observations leave sustained ordinary play open.
- [ ] Qualify the [prepared-lab owner-build/install/playtest checklist](PLAYTESTING.md)
      on fresh public inputs, then establish final player installation, ordinary
      controls and update/rollback steps. Retain
      [J888's device observations and teardown](history/journal-J1-J1177/PORTING_JOURNAL.md#j888--refuse-unknown-baseline-device-state-and-verify-teardown).
- [ ] Obtain explicit user approval for releases, outward announcements,
      repository settings and issue templates after preparing reviewable changes
      ([publication policy](ALPHA_POLICY.md#distribution-and-feedback)).
      Workstream pushes and PR merges are already authorized.
