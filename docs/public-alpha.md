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
      admitting a full texture cohort. [J1128](PORTING_JOURNAL.md#j1128--produce-complete-rgba-mip-and-source-cubemap-cohorts-on-the-host) qualifies all 1,523 RGBA mip-chain records
      and 110 source-derived Cubemaps on the host. Their Android production,
      13 native reflection cubes and complete bundle assembly remain open.
      [J1136](PORTING_JOURNAL.md#j1136--bound-native-cubemap-residue-with-omitted-original-pc-sources)
      tests omitted original scene/player sources without closing that residue;
      no replacement lighting or target pixels enter the producer.
      [J1113](PORTING_JOURNAL.md#j1113--produce-a-complete-source-only-bundle-and-seven-player-data-files)
      qualifies the first complete PC-only bundle and seven player-data files;
      J1135 extends the host cohort to nine complete bundles; the combined
      readiness tree includes 161 player files
      through the existing owners; 54 texture selections use PR75's landed
      public RGBA producer/profile. The fixed-target readiness check now
      has 517 missing content entries; all 18 code/SDK
