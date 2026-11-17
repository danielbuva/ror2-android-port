# ADR-002 — Preserve IL2CPP and investigate phone-only owner builds

Status: **accepted direction**, 2026-10-20. Findings reviewed 2026-11-17.
End-to-end phone installation remains unqualified.
This amends [ADR-001](ADR-001-port-architecture.md); its architecture C remains
the runtime implementation. The user's **Route A** means preserving that
native IL2CPP runtime, not ADR-001's source-reconstruction option A.

## Decision

Keep Unity **2021.3.45f2 (88f88f591b2e)**, IL2CPP ARM64 and the existing Android
rendering pipeline authoritative. Do not migrate gameplay to HybridCLR, Mono,
box64, another interpreter or another execution backend to simplify delivery.

First produce a playable source-derived build from the owner's legitimate PC
files. The first private device milestone uses title, lobby, the loading scene,
Titanic Plains, Distant Roost and Commando, with the dependencies those scenes
and survivor need. Qualify ordinary play on that build before validating the
complete phone-only flow without a Unity editor on the phone. Keep the desktop
owner-build workflow as a fallback.

The [phone owner-build assessment](phone-owner-build.md) maps editor requirements,
Android-capable tools and genuine blockers. [public-alpha.md](public-alpha.md)
holds open release work. Earlier [runtime-option research](history/public-alpha-distribution-options-2026-10-20.md)
is historical background only.

## Distribution and ownership

Publish audited original tooling, recipes and independently authored bootstrap
material. Owners supply legitimate input and generate all game-derived APK
code, metadata, shaders and content locally. Moving original AOT code into a
library, patch, archive or later download does not remove that constraint.
No project-hosted game build service is approved.

Open-source licenses must cover complete distributed tool dependencies. Unity
editor/compiler components, middleware and original game content remain separate
rights/input boundaries. Acquisition must retain ownership/Guard checks and
secret-safe handling; it does not establish original in-game Steam startup or
DLC entitlement. Local files must not be labelled an authenticated session.
Android and PC/cloud profiles retain their separate compatibility gates.

Device runs use the dispatcher queue and grant, exclusive device lease and
shared runner. The authorized serial stays in ignored configuration and is
explicit on every device action. Shared Unity builds retain the mandatory mutex.

## Findings review

- **Acquisition.** Host contracts cover folder/ZIP inventory, fingerprinting,
  cancellation and unknown-input refusal. Legitimate files still need Android
  qualification with actual Storage Access Framework providers and supported
  and unknown input cohorts. Account downloads and Steam Cloud remain deferred.
  See the [alpha acceptance contract](ALPHA_POLICY.md#final-flow-acceptance-contract).
- **Content and playability.** The converted APK reached the original-catalog
  Commando survivor menu. Separately, the Android toolhost emitted 290,498
  structurally validated records from a prepared request. The resulting bundle
  still needs Unity typed load and integration with its catalog and native
  manifest. The converted build still needs ordinary stage play, native End Run
  and comparison with the lab reference.
  [J1476](PORTING_JOURNAL.md#j1476--converted-apk-reaches-the-original-catalog-survivor-menu),
  [J1478](PORTING_JOURNAL.md#j1478--emit-the-strict-whole-game-content-request-on-android).
- **Code, tools and packaging.** Host contracts bind the admitted input
  inventory into a signed incremental release graph, connect conversion and
  native jobs, and feed converter outputs into player-data production. The
  Android app still needs to execute the integrated game-code, metadata, content,
  shader, SDK packaging and signing chain with permitted tool inputs. Bootstrap
  must work without private generated inputs or workstation analysis receipts.
  [#541](https://github.com/danielbuva/ror2-android-port/pull/541),
  [#542](https://github.com/danielbuva/ror2-android-port/pull/542),
  [#543](https://github.com/danielbuva/ror2-android-port/pull/543).
- **Install, update and recovery.** Android installed the synthetic alpha using
  system consent. Check for updates found the next version. An in-place update
  and higher-version rollback kept the signing certificate and synthetic files.
  A separate lab run replayed an interrupted native profile write across two
  cold Starts. The production alpha still needs native save/settings retention,
  interruption and cold-start recovery, and owner key recovery. Qualify a newer
  port release end to end, reusing unchanged outputs where possible.
  [J1482](PORTING_JOURNAL.md#j1482--verify-issued-alpha-versions-and-forward-rollback-on-android),
  [J1480](PORTING_JOURNAL.md#j1480--recover-an-interrupted-native-profile-commit).
- **Distribution.** Release artifacts are limited to audited public recipes,
  producers, permitted toolchain components and the installer. Close the
  remaining component grants and dependency audits before external publication,
  which still requires owner approval.
  [Tool and redistribution boundaries](phone-owner-build.md#tool-and-redistribution-boundaries).

## Acceptance

Pin and compare Unity and package versions, assembly transforms, compiler
options, stripping, shaders and actual build outputs. Require resolvable
PPtr/file IDs, valid serialized layouts and type trees, script bindings and
colliders, plus Unity typed load. Device acceptance requires ordinary gameplay
and matched behaviour, content, visuals and sustained performance/memory against
lab build `9f904392` (source `6c12b506`). Byte comparisons are diagnostic. The
[alpha checklist](public-alpha.md#decision-and-reproducibility) tracks the device
and final delivery gates separately from this review.
