# Public alpha checklist

Audited 2026-11-04 against merged journal J1300–J1359 and PRs #239–#326,
through [J1359](PORTING_JOURNAL.md#j1359--retained-sustained-game-performance-report)
and [PR #326](https://github.com/danielbuva/ror2-android-port/pull/326).
All 18 acceptance gates remain open; linked results establish partial progress.

The user accepts [owner-built Route A](ADR-002-public-alpha-distribution.md);
[ADR-001](ADR-001-port-architecture.md) retains Architecture C, native IL2CPP ARM64
and the current renderer. Phone-only owner builds are the installation target;
retain the desktop fallback. The [stage assessment](phone-owner-build.md) precedes
build-pipeline changes. This checklist makes no alpha-readiness claim.

## Decision and reproducibility

- [ ] Deliver complete PC-input-to-Android conversion on the phone, preserving
      Architecture C. Evaluate the [accepted-build design](accepted-build-reconstruction.md)
      against the full target before implementing another large pipeline.
      [J1357](PORTING_JOURNAL.md#j1357--resolve-source-derived-tree-windasset-endpoints)
      retains host readiness at 693/705 files, 685 raw-exact;
      [J1358](PORTING_JOURNAL.md#j1358--retain-audited-menu-build-identities-and-native-provider-order)
      leaves Menu/HUD differences and complete phone production/install/update open.
- [ ] Qualify permitted tool acquisition, Android app execution, complete game
      AOT/metadata construction, content/shader production, durable owner signing
      and user-mediated installation/update as one complete flow, including
      Check for updates. The [stage evidence](phone-owner-build.md) and
      [host-qualified installer integration](PORTING_JOURNAL.md#j1257--integrate-resumable-public-phone-installation-and-updates)
      do not establish complete game conversion or phone acceptance.
- [ ] Complete public-input bootstrap without private generated assets or
      workstation analysis receipts ([structural blockers](execution-backlog.md#structural-cleanup)).
      Reuse the [owner assembly prefix](OWNER_ASSEMBLIES.md); resolve remaining
      content/shader producers and [component distribution grants](phone-owner-build.md#tool-and-redistribution-boundaries).
- [ ] Qualify the complete owner-generated output on the selected alpha device,
      with committed source/input/toolchain receipts, ordinary installation/update
      and matched performance ([acceptance gates](phone-owner-build.md#proof-gates)).
      Preserve the original installation, Main's editor/build mutex/device and
      desktop fallback. IL2CPP alone does not prove equivalent performance.
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
      [J1358](PORTING_JOURNAL.md#j1358--retain-audited-menu-build-identities-and-native-provider-order)
      leaves Menu/HUD reconstruction differences and device acceptance open.
- [ ] Qualify physical end-run/results navigation and repeated-session memory
      ([session owners](ARCHITECTURE.md#ownership)).
      [J1342](PORTING_JOURNAL.md#j1342--restore-original-point-sound-timeout-dispatch)
      drains the instrumented audio timeout queue;
      [J1350](PORTING_JOURNAL.md#j1350--restore-original-console-retention-default-at-composed-startup)
      retains positive matched-menu growth after twelve assisted sessions.
      Ordinary long-run dependency retention remains open.
- [ ] Coordinate gameplay/audio/animation prerequisites with the main session;
      acceptance follows [capability gates](milestones.md), including an
      unassisted run. Keep Moon/finale manual.

## Performance (release gate)

Correctness comes first: no optimization may change reconstructed bytes, original
behaviour or visual output to improve a benchmark. Reconstruction-gap closure stays
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
