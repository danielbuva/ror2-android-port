# Public alpha checklist

Open work only. Remove completed items and record their results in the journal.
The user accepts [owner-built Route A](ADR-002-public-alpha-distribution.md);
[ADR-001](ADR-001-port-architecture.md) retains architecture C. This checklist
makes no alpha-readiness claim.

Phone-only owner builds are the installation research target; retain native
IL2CPP ARM64 and the current renderer, with desktop builds as fallback.
The [stage assessment](phone-owner-build.md) precedes build-pipeline changes.

Decision preparation: [J829](PORTING_JOURNAL.md#j829--research-public-alpha-distribution-before-choosing-a-launcher).

## Decision and reproducibility

- [ ] Resolve the editor-equivalent Android content/shader production gate without
      consuming desktop-generated game data as a hidden prerequisite; extend
      [J832's precursor](PORTING_JOURNAL.md#j832--run-the-exact-converter-on-android-and-load-content-built-without-a-template)
      to the full rendered/script-bound fixture; phone-side TextAsset generation
      is qualified in [J833](PORTING_JOURNAL.md#j833--generate-content-and-sign-increasing-fixture-updates-on-android).
- [ ] Establish permitted acquisition and Android execution of the exact IL2CPP
      tools beyond the authored converter proof; extend
      [J842’s converter/native fixture proof](PORTING_JOURNAL.md#j842--run-the-full-authored-converter-and-load-its-phone-compiled-native-output)
      through stripping/root production to the complete accepted game,
      app sandbox execution (including [J836’s unresolved refusal control](PORTING_JOURNAL.md#j836--build-an-authored-apk-on-android-and-test-app-host-execution)), complete packaging, durable owner signing-key
      custody and user-mediated installer/update flows beyond the fixture proof.
- [ ] Present bounded proof findings before changing the working build or choosing
      the final installation experience. Keep other execution backends excluded.
- [ ] Benchmark any alternative pipeline with pinned versions/options/shaders and
      matched device workloads; IL2CPP alone does not prove equivalent performance.
- [ ] Qualify the isolated owner-build environment; the alpha device is alpha's
      exclusive device per [J818](PORTING_JOURNAL.md#j818--qualify-thor-and-preserve-the-siren-guard-across-device-reassignment).
      Select it explicitly and install only an explicit alpha-built APK.
- [ ] Complete a public-input bootstrap with no private recipes, inherited
      workstation-only assets or analysis receipts
      ([structural blockers](execution-backlog.md#structural-cleanup),
      [J586](PORTING_JOURNAL.md#j586--r9-rerun-no-new-reimport-errors-one-gate-file-and-one-apk-shader-left)).
- [ ] Bind builds to committed source, accepted input and toolchain receipts
      ([J738](PORTING_JOURNAL.md#j738--whole-catalog-builds-stage-only-committed-sources-and-record-the-commit));
      qualify fresh owner-generated outputs on the alpha device.
- [ ] Audit public artifacts for game-derived material and separately licensed
      dependencies; keep all owner-generated content private.

## Packaging and acquisition

- [ ] Decide release package identity, increasing version code, private signing
      custody and update/rollback policy; prove profile/settings update retention.
- [ ] Implement approved local-file validation and, if selected, owned-account
      downloads with Steam Guard, cancellation, secret-safe logs and honest
      unknown-version refusals. Preserve the source installation.
- [ ] Keep Steam identity, unavailable services and expansion access truthful
      ([L5/L9](milestones.md)); record the Steam Cloud inclusion/deferral decision.
- [ ] Verify fresh capacity, package placement and runtime backing per device
      ([J595](PORTING_JOURNAL.md#j595--verify-the-scoped-current-nova-path-and-harden-receipt-cleanup),
      [J755](PORTING_JOURNAL.md#j755--onboard-the-additional-devices-with-separate-storage-ownership-and-roles)).

## Controls, UI and sessions

- [ ] Qualify ordinary physical input, original/native mappings and rebinding;
      automatic diagnostics do not qualify ordinary control
      ([J762](PORTING_JOURNAL.md#j762--accept-explicit-thor-game-diagnostics-and-unchanged-nova-controls)).
- [ ] Device-test touch movement, aim/camera, skills, equipment, interaction and
      menus, including pause/resume and held-input release.
- [ ] Inventory original screens against [subsystem coverage](subsystem-coverage.md);
      qualify menus, settings persistence and touch/controller navigation.
- [ ] Qualify end-run confirmation, teardown, results/return-menu and same-process
      restart with ordinary input ([session owners](ARCHITECTURE.md#ownership)).
- [ ] Coordinate gameplay/audio/animation prerequisites with the main session;
      acceptance follows [capability gates](milestones.md), including an
      unassisted run. Keep Moon/finale manual.

## Stability and playtests

- [ ] Attribute and bound repeated-session managed growth, then qualify a long
      device series ([open evidence](execution-backlog.md#stability-and-performance)).
- [ ] Qualify crash/ANR recovery, background/resume, interrupted writes, storage
      failure, sustained performance and thermals on supported hardware.
- [ ] Add tokenless feedback from settings: browser issue draft, separate redacted
      report preview/export and explicit attachment consent. Obtain approval
      before public issue-template or tracker changes.
- [ ] Provide a short owner-build/install/playtest checklist with artifact
      identity, known limits, rollback and consented feedback steps.
- [ ] Obtain explicit user approval for outward-facing pushes/PRs, releases,
      repository settings and issue templates after preparing reviewable changes.
