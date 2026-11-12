# Execution backlog

Open work only, re-audited 2026-11-11 UTC against merged evidence since #338,
through [#431](https://github.com/danielbuva/ror2-android-port/pull/431) and journal J1405.
No complete alpha gate closes. Gate status lives in
[milestones](milestones.md); release acceptance lives in [public alpha](public-alpha.md).
Completed records remain in the [journal](PORTING_JOURNAL.md) and
[historical backlog](history/execution-backlog-2026-10-16.md).

## Phone-only installation (P1)

- [ ] Close the three remaining whole-game record selectors: two Clips and one
      AssetBundle. The former 345-record frontier is closed except for these
      [three](PORTING_JOURNAL.md#j1347--reconstruct-whole-game-customrendertextures);
      supplier coverage does not prove a complete bundle.
- [ ] Assemble and qualify complete groups, bundles, scene/player/lab data and
      catalogs from public producers and legitimate current PC input, including
      managed subtype/reference closure and source Menu/HUD presentation. Preserve
      strict PPtr/file-ID, type-tree, script-binding and collider checks; qualify
      a playable APK against the latest lab build. The
      [partial typed native bundle](PORTING_JOURNAL.md#j1388--emit-and-typed-load-a-closed-source-native-bundle-subset)
      and [camera suppliers](https://github.com/danielbuva/ror2-android-port/pull/428)
      do not qualify complete outputs. Historical byte equality is diagnostic under
      the [converter contract](accepted-build-reconstruction.md).
- [ ] Qualify complete source-derived lighting/occlusion and rendered output
      in-game against the current lab reference. Where historical lighting
      tolerance is reported, use the shipped [ADR-003](ADR-003-lighting-tolerance.md)
      validator and actual numerical/visual evidence; no record has both admissions.
      Historical byte differences alone do not block playable conversion.
- [ ] Complete on-phone production without Unity on the phone, retaining IL2CPP,
      original behaviour and authorized toolchain/distribution boundaries.
- [ ] Qualify fresh install, in-place update with the same on-device signing key,
      save retention and **Check for updates** against a public release. Installer
      UI/release fetch/session install and manifest/incremental rebuild/signing
      must pass together; partial host or installer tests do not close P1.
- [ ] Complete public-input bootstrap without private generated assets or analysis
      receipts; resolve required tool/component distribution grants and finish the
      [ADR-002 findings review](ADR-002-public-alpha-distribution.md) before selecting
      a replacement pipeline or final installation architecture.

## Alpha acquisition and playtests

- [ ] Qualify actual SAF folder/ZIP providers with legitimate input cohorts:
      validation, cancellation and explicit supported/unknown-version handling.
      Keep the source installation read-only; follow the
      [acceptance matrix](ALPHA_POLICY.md#final-flow-acceptance-contract).
- [ ] Qualify final alpha identity, issued-version/same-key updates and forward
      rollback, including real profile/settings backup, verified restore,
      interruption and cold-start retention. Lab update hash retention in
      [J1401](PORTING_JOURNAL.md#j1401--load-typed-results-definitions-before-dependent-drop-tables)
      does not establish this complete flow.
- [ ] Qualify the [prepared-lab playtest checklist](PLAYTESTING.md) from fresh public
      inputs, then final player install, controls and update/rollback steps.
- [ ] Prepare reviewable release, announcement, repository-setting and issue-template
      changes and obtain the explicit approval required by
      [publication policy](ALPHA_POLICY.md#distribution-and-feedback).

## Stability and performance

- [ ] Attribute remaining managed retention and demonstrate a plateau, then run a
      sustained session. Matched assisted-session growth fell from about 680 to
      [219 KB/session](PORTING_JOURNAL.md#j1350--restore-original-console-retention-default-at-composed-startup);
      the positive slope remains open. Use the
      [final-menu heap](PORTING_JOURNAL.md#j1353--capture-the-requested-final-menu-heap)
      for attribution. Complete the long series with valid telemetry:
      [J1402](PORTING_JOURNAL.md#j1402--continue-memory-observations-through-native-loss-and-menu)
      stopped at ten completions; the later
      [32-session supervised diagnostic](PORTING_JOURNAL.md#j1407--preserve-cooldown-admission-readings-across-display-wake)
      completes, but final-16 matched-menu managed growth remains positive.
      The [32-session catalog-wrapper qualification](PORTING_JOURNAL.md#j1463--bound-collected-catalog-diagnostics-across-32-sessions)
      still grows 634,880 managed
      bytes over menus 18–33 (fitted +35,990.588 bytes/menu), with released catalog
      targets collected and two active locators. Attribute remaining owners using
      the existing paired native-heap capture; ordinary-play qualification stays open.
- [ ] Close the [performance release gate](public-alpha.md#performance-release-gate):
      profile converter time/memory/heat/storage per stage and sustained gameplay
      FPS, frame pacing, battery and visual fidelity; optimize measured costs
      without changing produced bytes, original behaviour or visual output.
      Startup now requests
      [300 FPS](https://github.com/danielbuva/ror2-android-port/pull/322);
      sustained 60 FPS acceptance remains open.
- [ ] Qualify physical mappings/rebinding, touchscreen equipment/target effects,
      hardware screen/results navigation and ordinary long-run dependency retention
      against the [input contract](INPUT_QUALIFICATION.md) and
      [screen inventory](SCREEN_COVERAGE.md).
- [ ] Complete real interrupted-write/power-cut, ENOSPC and remaining recovery cases,
      plus ordinary sustained performance/thermal cases on supported hardware
      ([alpha checklist](public-alpha.md#stability-and-playtests)).
- [ ] Integrate original position indicators and compare player/NPC/boss/nameplate
      output against matched PC captures (J787).

## Gameplay integration

- [ ] Resolve source-view color/lighting differences against a matched PC reference.
- [ ] Complete original audio mix, spatial/event attribution and audibility acceptance;
      preserve the qualified source clients and bounded release/restart (J1080).
- [ ] Complete an unassisted normal-difficulty run; current route evidence is assisted.
- [ ] Commit an actually earned alternate loadout through the profile; observe the
      remaining near-death charge, two-stack Mountain Shrine and loop achievements,
      plus ordinary positive unlock grants (J493/J503).
- [ ] Complete default and alternate base-survivor ability effects against the live
      variant inventories (J673/J684/J685).
- [ ] Observe natural teleporter/boss rewards and exit through the source-stage
      lifecycle, preserving source retirement and effect-reference guards.
- [ ] Identify the intermittent LightningStake NaN producer across projectile
      identity turnover; finite controls have not resolved it
      ([observer owner](ARCHITECTURE.md#lightningstake-source-call-observer)).
- [ ] Repair native navigation/recovery on the Siren route, then qualify exact egg
      interaction, boss start/defeat, rewards, MapZones, retirement and teardown.
- [ ] Play the nine staged DLC scenes after truthful expansion availability (J488).
- [ ] Moon/finale/escape: manual sessions only.

## Structural cleanup

Retain the open [architecture debt](ARCHITECTURE.md#known-structural-debt):

- [ ] Qualify functional rebuild/loadability (`Hidden/Compositing`) and replace
      remaining local runtime-contract/shader/inherited-content/provenance inputs; switch the working
      build to the rebuild path ([migration plan](migration-removal-plan.md)).
- [ ] Check provenance drift after accepted baselines and replay R1–R8 when needed.
- [ ] Have `Start` call `GameSession` directly; reduce shared coordinator state.
- [ ] Replace historical timestamped input dependencies with named receipts or retire
      those actions; move still-needed gameplay drivers into tracked owners.
