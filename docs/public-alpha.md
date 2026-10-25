# Public alpha checklist


The host-qualified [release update contract](../tools/phone-build/owner-apk/README.md#public-release-updates)
now covers per-entry incremental reuse and existing-key signing. Installer trust
provisioning, complete phone production and installed-game update retention remain open.
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
      [J1107](PORTING_JOURNAL.md#j1107--complete-host-rgba-production-and-bound-the-phone-thermal-refusal)
      qualifies all 1,333 remaining single-mip RGBA records on the host; its
      complete phone cohort remains open after
      [J1123](PORTING_JOURNAL.md#j1123--guarded-rgba-phone-batch-loses-transport-admission-stays-open)
      records the interrupted guarded run. Recovered evidence review and a
      checkpointed single-job rerun are required.
      [J1110](PORTING_JOURNAL.md#j1110--produce-every-etc1-mip-chain-from-original-pc-textures-on-the-host)
      qualifies all 1,589 ETC1 mip-chain records on the host, with Android
      qualification open. [J1140](PORTING_JOURNAL.md#j1140--qualify-the-bounded-android-tool-guard-and-checkpoint-recovery)
      qualifies bounded Android guard and checkpoint-recovery controls, without
      admitting a full texture cohort.
      [J1158](PORTING_JOURNAL.md#j1158--rgba-phone-cohort-interrupted-by-recorded-hangup)
      records the next interrupted cohort: host ADB is killed, the guard records
      hangup, and full phone qualification remains open. Separate recovery
      preserves the interrupted checkpoint, verifies idle state and unchanged
      installed bytes, removes owned scratch and releases the device.
      [J1173](PORTING_JOURNAL.md#j1173--preserve-the-rgba-phone-prefix-after-bounded-wall-timeout)
      preserves 506 verified records after the retry wall timeout; a complete
      source-only phone cohort remains open.
      [J1128](PORTING_JOURNAL.md#j1128--produce-complete-rgba-mip-and-source-cubemap-cohorts-on-the-host) qualifies all 1,523 RGBA mip-chain records
      and 110 source-derived Cubemaps on the host. Their Android production,
      13 native reflection cubes and complete bundle assembly remain open.
      [J1136](PORTING_JOURNAL.md#j1136--bound-native-cubemap-residue-with-omitted-original-pc-sources)
      tests omitted original scene/player sources without closing that residue;
      no replacement lighting or target pixels enter the producer.
      [J1165](PORTING_JOURNAL.md#j1165--bound-historical-input-drift-in-native-snowy-cubemaps)
      also excludes the retained historical Snowy triplet: none reproduces J850,
      so those records remain outside drift-explained qualification.
      [J1113](PORTING_JOURNAL.md#j1113--produce-a-complete-source-only-bundle-and-seven-player-data-files)
      qualifies the first complete PC-only bundle and seven player-data files;
      J1139 supplies 173 complete player files, including source-derived TMP
      hashes and native selection manifests. J1163 extends the independently
      produced payload cohort to twenty-two complete bundles. The shared source
      tree preserves J1157's complete host Shader cohort. The combined
      fixed-target readiness check has 118 missing content entries; all 18 code/SDK
      entries are available. Phone replay, the
      remaining bundles/player data and complete source-derived installation
      remain open; the structural writer produces no missing content itself.
      J1155 additionally qualifies the unchanged current-original Windows
      comparison-bundle copy as drift-explained, separately from exact output.
      Its admission through the public input-drift checker is a host
      control; no historical file becomes a reconstruction input.
      [J1081](PORTING_JOURNAL.md#j1081--run-owner-supplied-standalone-sdk-tools-through-a-public-android-runner)
      qualifies a reproducible public Android runner for standalone SDK build
      tools. The full Linux RGBA cohort, original shader/content production and ordinary
      owner delivery remain open; game execution remains native IL2CPP ARM64.
      [J1094](PORTING_JOURNAL.md#j1094--qualify-exact-sdk-vulkan-shader-compilation-on-android)
      qualifies exact host/phone authored Vulkan shader-tool output. Phone
      original-shader recovery and app integration remain open. J1157 qualifies
      all 414 APK Shader48 objects through source-only host
      production: 369 complete files plus two shared records. The combined
      source tree has 587 of 705 entries available (582 raw-exact, two code
      comparison entries and three separately drift-explained); 118 remain
      missing (J1163). Host shared mixed-file assembly is qualified; phone serialization remains open.
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
The policy's [acceptance matrix](ALPHA_POLICY.md#final-flow-acceptance-contract)
separates reusable host owners from final-flow work; it does not qualify an
installed alpha package.

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
      use the [measured-input contract](INPUT_QUALIFICATION.md).
      Automatic diagnostics do not qualify ordinary control
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
      The old-heap graph fingerprint and host-only queued-case qualification are
      recorded in [J1122](PORTING_JOURNAL.md#j1122--prepare-alpha-host-contracts-and-identify-an-old-heap-fingerprint).
- [ ] Complete real interrupted-write/ENOSPC and sustained performance/thermal
      cases on supported hardware. [J1071](PORTING_JOURNAL.md#j1071--qualify-software-touch-native-pause-and-recovery)
      qualifies controlled VM-crash and genuine ANR cold recovery, invalid-pending
      refusal, validated-backup recovery, directory-write failure/retry and fresh
      background return. J1127 stops cold startup at the CPU thermal threshold
      before any interrupted-write, heap or sustained stage completes. J1130 confirms
      unreadable thermal interfaces;
      [J1131](PORTING_JOURNAL.md#j1131--supervise-all-readable-gameplay-thermal-zones)
      host-qualifies the clarified readable-zone admission/runtime policy.
      [J1137](PORTING_JOURNAL.md#j1137--separate-thermal-admission-discovery-from-runtime-sampling)
      separates admission discovery from strict runtime sampling after a prelaunch
      timeout.
      [J1141](PORTING_JOURNAL.md#j1141--exclude-unavailable-admission-thermal-sentinels)
      host-qualifies the revised admission-only unavailable-sentinel policy;
      previously valid sensors becoming sentinels still abort gameplay.
      [J1148](PORTING_JOURNAL.md#j1148--restrict-gameplay-admission-to-cpu-gpu-battery-and-skin)
      host-qualifies the revised CPU/GPU/battery/skin admission scope. Fresh
      device qualification remains open; J1156 below updates the runtime limits.
      [J1156](PORTING_JOURNAL.md#j1156--qualify-per-zone-gameplay-thermal-duration-and-limits)
      host-qualifies per-zone core duration and immediate core/battery/skin
      runtime limits after J1152's startup spike; fresh gameplay qualification
      remains open.
      [J1164](PORTING_JOURNAL.md#j1164--recover-an-interrupted-native-save-and-classify-stage-load-thermal-refusal)
      qualifies native pending-write interruption/recovery on the installed R58.
      Its next stage is deliberately stopped by the sustained CPU thermal guard
      during stage startup; fresh heaps and sustained play remain open.
      Injected persistence states and this writer interruption do not establish
      a power-cut or filled-filesystem result.
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
bytes exact. The guarded startup-affinity rerun completes with a 79.2 C peak and
340 ms maximum sampling gap, meeting the short-job thermal protocol; the earlier
95.5 C failure remains recorded. Complete content composition, sustained thermal
qualification and final installation remain open.

The owner APK assembler accepts the complete 15-entry SDK output cohort alongside
the three mandatory IL2CPP/metadata/Burst files through its existing explicit
`code` mapping. Host fixtures assemble all 18 outputs without replay files and
check produced-manifest routing, source drift and partial-cohort refusal. This
wiring does not close complete phone composition, installation, controls or
matched performance.

[J1112](PORTING_JOURNAL.md#j1112--inventory-final-owner-apk-inputs-before-launcher-compilation) records the current assembler's `--check-request` inventories the complete final target
tree and explicit code cohort before launcher compilation. It reports every
absent/mismatched content file and raw code difference, while retaining false
source-provenance and device-qualification fields. Object/resource packs from
the content producers still require bundle/player-data assembly; the complete
source-derived tree and corrected phone-native output remain open. A separate
host composition/signing validation passes with produced host code/SDK and
explicit replay content; it does not qualify phone production or installation.

[J1114](PORTING_JOURNAL.md#j1114--produce-both-generic-android-build-metadata-files)
closes the two generic Android build-metadata producer gaps. Fresh host SDK
production yields all 15 entries raw-exact to J850. Final-file availability and
raw equality remain separate from source provenance,
phone production and runtime acceptance. J1153 records the current exact,
drift-explained and missing cohorts; the checker preserves actual admitted
current bytes. Ordinary-app metadata qualification, corrected phone-native
output, complete content, installation, controls and matched performance remain
open.

[J1133](PORTING_JOURNAL.md#j1133--produce-source-animation-hierarchy-and-generic-records-on-the-host)
extends the source-only object producers. These host-qualified packs still
require complete bundle/player-file assembly and ordinary-app qualification;
they do not independently close a final-file readiness entry.

[J1149](PORTING_JOURNAL.md#j1149--produce-current-english-and-font-material-with-explained-input-drift)
adds current-input English and the fifth font material through the same player
owner. Historical originals qualify the transformation; reconstruction consumes
the current installation only. Their complete byte differences are explained by
original-input drift and remain separate from exact J850 matching.
J1153 adds the explicit checker classification through pinned historical exact,
repeated current and complete input/output difference evidence. Exact and
drift-explained counts remain separate, and assembly preserves the current
supplier bytes and payload-index hashes. The checker never reads historical
originals or outputs; causal lineage and independent invocations still need
review of the raw producer receipts. Phone qualification remains open.

J1154 collects the phone native job's failed terminal timeout at compilation
job 498. Its retained successful objects may support checked continuation;
complete phone-native production, ordinary installation, both controls and
matched first-stage performance remain open.

[J1143](PORTING_JOURNAL.md#j1143--qualify-expanded-source-animation-controller-and-graph-records) qualifies expanded
source animation/controller and checked hierarchy graph packs on the host.
They add no complete final-file readiness entry or APK destination record.
Complete file assembly and ordinary-app production remain required.

[J1162](PORTING_JOURNAL.md#j1162--retain-the-native-measurement-transport-failure-and-refresh-source-readiness)
updates current host readiness to 583 of 705 files: 578 raw-exact, two produced
code outputs requiring separate comparisons and three drift-explained files.
Seven APK files and 115 payload files remain missing; current-only assembly,
phone production and runtime qualification remain open. The native measurement
attempt stops on a host ADB stream SIGKILL during tool-host compilation, before
any native timings. Its sender is unknown; cleanup verifies stopped tools,
sleeping panels and lease release.

[J1167](PORTING_JOURNAL.md#j1167--measure-representative-native-compilation-on-the-phone) completes the three representative ordinary-app native compiler timings.
They size the active-time budget for checked continuation from 498 retained
objects; complete native production, final assembly and game qualification
remain open.

J1168 records the first continuation failure before compilation: Android
Python lacks `os.link`. A receipt-checked copy fallback passes host contracts;
full phone native production and gameplay qualification remain open.

[J1161](PORTING_JOURNAL.md#j1161--assemble-the-complete-player-script-registry-and-default-scene-shared-file)
adds complete source-derived script-registry and default-scene files through the
existing player owner. Its 177-file host cohort has 175 raw-exact files and two
current-input differences; complete host availability is 583 of 705 files.
[J1169](PORTING_JOURNAL.md#j1169--bound-the-complete-source-only-player-registry-metadata-lifetime) closes the host metadata memory gate;
a fresh bounded phone replay remains open.
[J1159](PORTING_JOURNAL.md#j1159--phone-player-assembly-refuses-an-omitted-original-shader-input)
records the separate phone replay's incomplete staging;
[J1166](PORTING_JOURNAL.md#j1166--guarded-phone-player-assembly-stops-on-thermal-limit)
records its repaired retry's thermal stop and verified cleanup. No complete
phone comparison or installation is qualified.
