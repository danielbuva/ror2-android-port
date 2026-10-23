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

- [ ] Complete accepted-input export on Android within explicit resource limits
      and compare actual project outputs. Follow
      [J1008's failed full-import evidence](PORTING_JOURNAL.md#j1008--bound-android-assetripper-startup-and-full-input-import-failures)
      with [J1016's raw/materialization distinction](PORTING_JOURNAL.md#j1016--separate-raw-retention-from-incomplete-android-asset-materialization).
      [J1018's direct-API/reference-release controls](PORTING_JOURNAL.md#j1018--test-consumed-buffer-ownership-during-android-asset-materialization)
      still fail complete materialization. Use the planned partial graph to test
      loading overlap; complete graph ownership and the native failure remain
      open. Partial-graph, narrow ownership or raw-loading results do not pass
      this gate.
- [ ] Resolve the editor-equivalent Android content/shader production gate without
      consuming desktop-generated game data as a hidden prerequisite; extend
      [J832's precursor](PORTING_JOURNAL.md#j832--run-the-exact-converter-on-android-and-load-content-built-without-a-template)
      to the full rendered/script-bound fixture; phone-side TextAsset generation
      is qualified in [J833](PORTING_JOURNAL.md#j833--generate-content-and-sign-increasing-fixture-updates-on-android).
- [ ] Establish permitted acquisition and Android execution of the exact IL2CPP
      tools beyond the authored converter proof; extend
      [J842’s converter/native fixture proof](PORTING_JOURNAL.md#j842--run-the-full-authored-converter-and-load-its-phone-compiled-native-output)
      through [J849's connected stripping/conversion](PORTING_JOURNAL.md#j849--feed-actual-phone-stripping-output-into-the-exact-converter), editor-root production and the complete accepted game,
      app sandbox execution (including [J836’s unresolved refusal control](PORTING_JOURNAL.md#j836--build-an-authored-apk-on-android-and-test-app-host-execution)), complete packaging, durable owner signing-key
      custody and user-mediated installer/update flows beyond the fixture proof.
- [ ] Present bounded proof findings before changing the working build or choosing
      the final installation experience. Keep other execution backends excluded.
      Extend [J857's complete pinned native metadata](PORTING_JOURNAL.md#j857--recover-the-complete-pinned-native-registry-from-owner-sdk-metadata-literals)
      through independent project scene usage, general module policy and exact root
      outputs. [J859](PORTING_JOURNAL.md#j859--generate-sdk-native-root-metadata-on-android-and-preserve-strippingconversion)
      qualifies native-table generation at the stripping boundary;
      [J862](PORTING_JOURNAL.md#j862--derive-authored-fixture-module-policy-from-owner-sdk-and-package-data-on-android)
      adds restricted fixture SDK/package-derived module policy. Captured scene
      roots and managed compilation remain explicit inputs.
      [J864](PORTING_JOURNAL.md#j864--read-persistent-native-class-ids-from-the-pinned-sdk-on-android)
      adds class-ID metadata. Following
      [J866's scoped metadata qualification](PORTING_JOURNAL.md#j866--qualify-scoped-sdk-assembly-metadata-and-forwarding-on-android)
      and [J869's SDK search metadata](PORTING_JOURNAL.md#j869--decode-pinned-sdk-wrapper-search-order-on-android),
      qualify wrapper-metadata consumer semantics and scene/manager usage with
      independent producers. Preserve
      [J873's direct-name/cache-query distinction](PORTING_JOURNAL.md#j873--separate-direct-scene-names-from-sdk-wrapper-cache-queries);
      the independent desktop oracle must never become a phone-build input.
      Extend [J876's native flag metadata](PORTING_JOURNAL.md#j876--decode-native-sdk-type-flags-on-android)
      through complete cache-consumer semantics before root production.
      [J878](PORTING_JOURNAL.md#j878--reconstruct-sdk-wrapper-population-on-android-with-a-complete-forward-oracle)
      verifies supported forward queries.
      [J883](PORTING_JOURNAL.md#j883--include-the-object-root-and-match-android-metadata-to-native-sdk-caches)
      matches root-inclusive Android metadata to native SDK cache observations;
      [J893](PORTING_JOURNAL.md#j893--observe-authored-scene-and-manager-dependencies-without-conflating-native-identities)
      adds separate desktop scene/manager observations and bounded type-name
      comparison. Produce native usage identities, scene labels and exact linker
      roots independently; keep SDK oracle reports out of phone generation.
      Extend [J895's manager declaration metadata](PORTING_JOURNAL.md#j895--read-sdk-manager-registration-declarations-on-android-and-preserve-retention-boundaries)
      through target/state-dependent serialization and native scene retention;
      asset-dependency exclusions alone do not determine class usage.
      [J934's Android feature declarations](PORTING_JOURNAL.md#j934--read-android-sdk-feature-declarations-and-compare-independent-api-observations)
      supply another static prerequisite; qualify target discovery, module
      inclusion and live state independently before claiming target retention.
      Preserve [J939's static-input/API-lookup distinction](PORTING_JOURNAL.md#j939--read-sdk-target-key-input-bindings-on-android-and-preserve-lookup-mismatches)
      while proving constructor results, map consumers and live availability.
      [J948's field operand alignment](PORTING_JOURNAL.md#j948--link-sdk-target-record-copy-and-consumer-operands-on-android)
      leaves node selection, container semantics and those live decisions open.
- [ ] Extend [J899's authored compiler fixture](PORTING_JOURNAL.md#j899--compile-an-authored-c-fixture-on-android-and-preserve-cross-host-output-differences)
      through general defines/generators, real source semantics and downstream
      stripping/conversion. [J902](PORTING_JOURNAL.md#j902--compile-the-authored-unity-fixture-with-sdkpackage-derived-references-on-android)
      derives the restricted fixture's references and compiles its Unity API
      source on Android; broader packages/player compilation remain open.
      [J905](PORTING_JOURNAL.md#j905--feed-the-android-compiled-unity-fixture-into-a-separate-stripping-handoff)
      separately strips those actual Android outputs.
      [J920](PORTING_JOURNAL.md#j920--convert-the-android-compiled-and-stripped-fixture-without-relaxing-replay-gates)
      converts them on Android with matching raw source/data outputs.
      [J921](PORTING_JOURNAL.md#j921--construct-and-load-the-authored-player-from-actual-android-compilerstripperconverter-outputs)
      connects the separate native/player consumer through device load/update
      checks. Extend beyond the fixed fixture while keeping captured scene
      roots explicit and the earlier exact-replay gate intact.
      Preserve the observed desktop/Android implementation DLL/PDB inequality
      and compiler-host distinction; a matching reference assembly alone does
      not establish equivalent behavior or performance.
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
- [ ] Add tokenless feedback from settings: browser issue draft, separate redacted
      report preview/export and explicit attachment consent. Obtain approval
      before public issue-template or tracker changes. The separate
      [host baseline preview](BASELINE_FEEDBACK.md) selects fixed facts for manual
      review; settings, arbitrary-log redaction and attachment export remain open.
- [ ] Provide a short owner-build/install/playtest checklist with artifact
      identity, known limits, rollback and consented feedback steps. Retain
      [J888's checked device observations and teardown](PORTING_JOURNAL.md#j888--refuse-unknown-baseline-device-state-and-verify-teardown)
      when extending the standard checks.
- [ ] Obtain explicit user approval for outward-facing pushes/PRs, releases,
      repository settings and issue templates after preparing reviewable changes.
