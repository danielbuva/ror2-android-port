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

- [ ] Deliver complete PC-input-to-Android conversion on the phone, preserving
      Architecture C. Evaluate the [fixed accepted-build design](accepted-build-reconstruction.md)
      against the full target before implementing another large pipeline.
      [J1042](PORTING_JOURNAL.md#j1042--reconstruct-the-complete-accepted-output-on-android)
      completes private delta/frame replay; independent input-only production and
      an Android-qualified installation/launcher flow remain open.
      [J1049](PORTING_JOURNAL.md#j1049--assemble-and-sign-the-complete-private-owner-apk-bootstrap-candidate)
      supplies the private host-built/signed bootstrap candidate.
      [J1065](PORTING_JOURNAL.md#j1065--qualify-private-owner-apk-preparation-upgrade-and-unity-lifecycle)
      qualifies its device preparation, update retention, Unity lifecycle and
      assisted controls. Phone-side signing, ordinary installer UX and
      independent production remain open.
      [J1063](PORTING_JOURNAL.md#j1063--complete-the-source-input-host-native-owner-build) completes public source-input host game-code
      production through a fresh native library. Explicit licensed SDK native
      input, full content/Burst/shaders and phone qualification remain gates.
      [J1070](PORTING_JOURNAL.md#j1070--produce-the-accepted-mesh-cohort-from-original-pc-bundles-on-android)
      qualifies source-only phone mesh production; two meshes, other content
      classes and complete bundle assembly remain open. Its output is not an
      installable target or a replacement for the private replay packet.
      [J995](PORTING_JOURNAL.md#j995--integrate-the-public-transform-profile-with-owner-prefix-and-portable-cli)
      qualifies an optional public .NET 8 transform profile: all 98 host prefix
      files and the three portable Android golden DLLs match. Complete game
      compiler/native production and app delivery remain separate gates.
      Full Unity-project reconstruction or AssetRipper export is not an assumed
      requirement. Every protected APK/payload output needs an owner-input
      producer; the accepted build supplies validation, never hidden target bytes.
- [ ] Resolve permitted tool acquisition and Android app execution, complete
      game AOT/metadata construction, Android content/shader production, durable
      owner signing and user-mediated installation/update as one complete flow.
      The [existing stage evidence](phone-owner-build.md) and
      [J921's connected authored-player chain](PORTING_JOURNAL.md#j921--construct-and-load-the-authored-player-from-actual-android-compilerstripperconverter-outputs)
      are reusable ingredients, not completion of the game converter.
- [ ] Complete public-input bootstrap without private generated assets or
      workstation analysis receipts ([structural blockers](execution-backlog.md#structural-cleanup)).
      Reuse the [owner assembly prefix](OWNER_ASSEMBLIES.md); resolve the remaining
      shader/inherited-content producers and all component distribution grants.
- [ ] Qualify the complete owner-generated output on the explicitly selected
      alpha device, with committed source/input/toolchain receipts, normal
      installer/update behavior and matched performance. Preserve the original
      game installation, Main's editor/build mutex/device and the desktop fallback.
      IL2CPP alone does not prove equivalent performance.
- [ ] Present findings before adopting a replacement build pipeline or final
      installation architecture. Keep other gameplay execution backends excluded;
      audit public artifacts and keep owner-generated game content private.

## Packaging and acquisition

[ALPHA_POLICY.md](ALPHA_POLICY.md) records the local-file-only acquisition,
separate alpha identity, owner signing/update/rollback and cloud deferral
decisions. The following items are implementation and acceptance gates.

- [ ] Enforce the selected alpha identity, increasing version code, private
      signing custody and update/rollback policy; prove actual game
      profile/settings update retention.
- [ ] Implement the selected local-file validation, cancellation and honest
      unknown-version refusals in the final owner flow. Preserve the source
      installation; account downloads and Steam Cloud are deferred by policy.
- [ ] Verify fresh capacity, package placement and runtime backing per device
      ([J595](PORTING_JOURNAL.md#j595--verify-the-scoped-current-nova-path-and-harden-receipt-cleanup),
      [J755](PORTING_JOURNAL.md#j755--onboard-the-additional-devices-with-separate-storage-ownership-and-roles)).

## Controls, UI and sessions

- [ ] Qualify ordinary physical input, original/native mappings and rebinding;
      automatic diagnostics do not qualify ordinary control
      ([J762](PORTING_JOURNAL.md#j762--accept-explicit-thor-game-diagnostics-and-unchanged-nova-controls)).
- [ ] Device-test touch movement, aim/camera, skills, equipment, interaction and
      menus, including pause/resume and held-input release.
- [ ] Qualify the [inventoried player screens](SCREEN_COVERAGE.md), menus,
      settings persistence and touch/controller navigation against
      [subsystem coverage](subsystem-coverage.md).
- [ ] Qualify end-run confirmation, teardown, results/return-menu and same-process
      restart with ordinary input ([session owners](ARCHITECTURE.md#ownership)).
      Device-test [J914's dependency-lifetime candidate](PORTING_JOURNAL.md#j914--retain-the-declared-audio-content-dependencies-across-session-cleanup)
      against J915's genuine next-menu failure, including default-off cleanup,
      original audio termination and repeated-session memory.
- [ ] Coordinate gameplay/audio/animation prerequisites with the main session;
      acceptance follows [capability gates](milestones.md), including an
      unassisted run. Keep Moon/finale manual.

## Stability and playtests

- [ ] Attribute and bound repeated-session managed growth, then qualify a long
      device series ([open evidence](execution-backlog.md#stability-and-performance)).
- [ ] Qualify crash/ANR recovery, background/resume, interrupted writes, storage
      failure, sustained performance and thermals on supported hardware.
- [ ] Qualify the [prepared-lab owner-build/install/playtest checklist](PLAYTESTING.md)
      on fresh public inputs, then establish final player installation, ordinary
      controls and update/rollback steps. Artifact identity, known limits and
      reviewed feedback are documented; those acceptance gates remain open. Retain
      [J888's checked device observations and teardown](PORTING_JOURNAL.md#j888--refuse-unknown-baseline-device-state-and-verify-teardown)
      when extending the standard checks.
- [ ] Obtain explicit user approval for releases, outward announcements,
      repository settings and issue templates after preparing reviewable changes.
      Workstream pushes and PR merges are already authorized.
