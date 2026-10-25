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
      assisted controls. [J1095](PORTING_JOURNAL.md#j1095--retain-one-on-device-owner-key-across-separate-apk-signing-builds)
      qualifies durable on-device key reuse/signing for authored APKs.
      [J1103](PORTING_JOURNAL.md#j1103--produce-fixed-target-burst-and-sign-owner-apks-in-the-android-tool-host)
      additionally qualifies ordinary-app signing and fixed-target Burst production:
      all 20 runtime sections and fresh linker roots match J850. Full-player
      assembly/signing, Android packaging members, ordinary installer UX and
      independent complete production remain open.
      [J1063](PORTING_JOURNAL.md#j1063--complete-the-source-input-host-native-owner-build) completes public source-input host game-code
      production through a fresh native library. Explicit licensed SDK native
      input, full content/shaders and source-only native phone qualification remain gates.
      [J1098](PORTING_JOURNAL.md#j1098--preserve-recorded-object-order-for-the-fixed-target-native-link) closes the host J850 native runtime-byte gap by retaining
      recorded link order; all 23 runtime sections and metadata match, with
      debug-link/build-ID differences retained. Phone native completion and
      corrected linking remain open.
      [J1070](PORTING_JOURNAL.md#j1070--produce-the-accepted-mesh-cohort-from-original-pc-bundles-on-android)
      qualifies source-only phone mesh production; two meshes, other content
      classes and complete bundle assembly remain open. Its output is not an
      installable target or a replacement for the private replay packet.
      [J1075](PORTING_JOURNAL.md#j1075--produce-every-accepted-avatar-from-original-pc-bundles-on-android)
      qualifies all 228 Avatar records from original PC bundles on Android.
      Textures, animation, shaders, other classes and complete bundle assembly
      remain open; these private packs add no game/runtime acceptance.
      [J1079](PORTING_JOURNAL.md#j1079--complete-uncompressed-texture-production-from-pc-bundles-on-android)
      qualifies all 399 uncompressed texture records and their public-source
      JPEG-tool build on Android; compressed texture/content formats stay open.
      [J1082](PORTING_JOURNAL.md#j1082--produce-the-complete-alpha8-texture-cohort-from-pc-bundles-on-android)
      qualifies 4,326 source Alpha8 texture records and their public codec build
      on Android. Other compressed textures, mip/cubemap and complete bundles
      remain open; these packs add no game-runtime acceptance.
      [J1088](PORTING_JOURNAL.md#j1088--produce-every-single-mip-etc1-texture-from-pc-bundles-on-android)
      qualifies all 281 ETC1/single-mip records and the shared public codec build
      on Android, with all 5,006 RGB/Alpha8/uncompressed records reverified.
      Remaining compressed textures, mips, cubemaps and complete bundles stay open.
      [J1081](PORTING_JOURNAL.md#j1081--run-owner-supplied-standalone-sdk-tools-through-a-public-android-runner)
      qualifies a reproducible public Android runner for standalone SDK build
      tools. The full Linux RGBA cohort, original shader/content production and ordinary
      owner delivery remain open; game execution remains native IL2CPP ARM64.
      [J1094](PORTING_JOURNAL.md#j1094--qualify-exact-sdk-vulkan-shader-compilation-on-android)
      qualifies exact host/phone authored Vulkan shader-tool output. Original
      shader recovery, variants, serialization and app integration remain open.
      [J1102](PORTING_JOURNAL.md#j1102--qualify-linked-vulkan-fragment-output-and-explicit-owner-apk-code-inputs)
      confirms both executable stages in that linked payload and accepts all
      three produced code outputs in the existing APK owner without replay
      fallback. Full-player phone assembly/install acceptance remains open; J1103
      qualifies the separate source-derived Burst producer.
      Owner-build v1 targets the single accepted J850 build through explicit
      profiles; promotion to a newer accepted target follows end-to-end proof.
      [J995](PORTING_JOURNAL.md#j995--integrate-the-public-transform-profile-with-owner-prefix-and-portable-cli)
      qualifies an optional public .NET 8 transform profile: all 98 host prefix
      files and the three portable Android golden DLLs match. Complete game
      compiler/native production and app delivery remain separate gates.
      [J1074](PORTING_JOURNAL.md#j1074--qualify-the-integrated-public-transform-tools-inside-the-android-app-host)
      qualifies current Python/.NET app hosting for those three DLLs, including
      cold attempts and input refusal. Full-player tool delivery, native/content
      production and the complete owner installation remain open.
      [J1084](PORTING_JOURNAL.md#j1084--run-whole-player-stripping-conversion-and-arm64-compilation-in-the-android-tool-host)
      qualifies the supplied-provider Android backend control; its corrected
      link remains separate, native bytes differ, and independent J850 managed
      production, final assembly/installation and performance remain open.
      Full Unity-project reconstruction or AssetRipper export is not an assumed
      requirement. Every protected APK/payload output needs an owner-input
      producer; the accepted build supplies validation, never hidden target bytes.
      [J1027's importer configuration controls](PORTING_JOURNAL.md#j1027--bind-explicit-importer-configuration-and-reject-drift-on-android)
      pass on Android. [J1029's actual-input call](PORTING_JOURNAL.md#j1029--preserve-a-native-importer-failure-during-raw-loading)
      fails during raw loading while formatting an earlier exception. Complete
      return/export and output equivalence remain unqualified.
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
Fresh per-device capacity, placement and runtime-backing receipts and capacity
refusal are qualified in [J1071](PORTING_JOURNAL.md#j1071--qualify-software-touch-native-pause-and-recovery),
retaining J595/J755's ownership guards. Final alpha identity and installation
qualification remain separate from these laboratory installs.

## Controls, UI and sessions

- [ ] Qualify ordinary physical input, original/native mappings and rebinding;
      automatic diagnostics do not qualify ordinary control
      ([J762](PORTING_JOURNAL.md#j762--accept-explicit-thor-game-diagnostics-and-unchanged-nova-controls)).
- [ ] Qualify the physical touchscreen digitizer, acquired-equipment activation
      and genuine target interaction. [J1071](PORTING_JOURNAL.md#j1071--qualify-software-touch-native-pause-and-recovery)
      qualifies software touch movement/camera, four native skill consumers,
      eight bank actions, cancellation, native menus/pause/release and fresh
      same-session background return; empty-slot/target requests are bank-only.
- [ ] Qualify ordinary navigation and remaining [inventoried player screens](SCREEN_COVERAGE.md)
      against [subsystem coverage](subsystem-coverage.md). J1066/J1071 qualify
      native settings, reviewed feedback and bounded persistence/recovery;
      complete source presentation and hardware navigation remain open.
- [ ] Qualify ordinary physical end-run/results navigation and repeated-session
      memory ([session owners](ARCHITECTURE.md#ownership)). J1066/J1071 qualify
      software confirmation/cancel, native teardown/menu and strict assisted
      same-process restart. J1080 qualifies Main's original audio Term/disarm;
      long-run dependency retention remains open.
- [ ] Coordinate gameplay/audio/animation prerequisites with the main session;
      acceptance follows [capability gates](milestones.md), including an
      unassisted run. Keep Moon/finale manual.

## Stability and playtests

- [ ] Attribute and bound repeated-session managed growth, then qualify a long
      device series ([open evidence](execution-backlog.md#stability-and-performance)).
      [J1100](PORTING_JOURNAL.md#j1100--complete-twelve-corrected-commando-sessions-and-retain-a-smaller-growth-frontier)
      completes 12 corrected Commando sessions, reducing matched menu growth to
      0.579 MiB/session; the remaining positive slope still prevents a full bound.
- [ ] Complete real interrupted-write/ENOSPC and sustained performance/thermal
      cases on supported hardware. [J1071](PORTING_JOURNAL.md#j1071--qualify-software-touch-native-pause-and-recovery)
      qualifies controlled VM-crash and genuine ANR cold recovery, invalid-pending
      refusal, validated-backup recovery, directory-write failure/retry and fresh
      background return. Injected persistence states do not establish a power-cut
      or filled-filesystem result.
- [ ] Qualify the [prepared-lab owner-build/install/playtest checklist](PLAYTESTING.md)
      on fresh public inputs, then establish final player installation, ordinary
      controls and update/rollback steps. Artifact identity, known limits and
      reviewed feedback are documented; those acceptance gates remain open. Retain
      [J888's checked device observations and teardown](PORTING_JOURNAL.md#j888--refuse-unknown-baseline-device-state-and-verify-teardown)
      when extending the standard checks.
- [ ] Obtain explicit user approval for releases, outward announcements,
      repository settings and issue templates after preparing reviewable changes.
      Workstream pushes and PR merges are already authorized.

J1109 qualifies all 13 generic Android package entries from pinned SDK/public
tools on the host, raw byte-identical to J850. Ordinary Android app-host production
also succeeds: 11 entries are raw-exact; the other two DEX files differ only in
compiler-generated class checksums and derived DEX headers, with all remaining
bytes exact. Startup reaches 95.5 C before the guard pauses the jobs; startup CPU
affinity is being qualified separately. Complete content composition, thermal
qualification and final installation remain open.
