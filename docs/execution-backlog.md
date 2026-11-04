# Execution backlog

Open work only, reconciled through PR #325 (2026-11-04 UTC). Gate status lives in
[milestones](milestones.md); release acceptance lives in [public alpha](public-alpha.md).
Completed records remain in the [journal](PORTING_JOURNAL.md) and
[historical backlog](history/execution-backlog-2026-10-16.md).

## Phone-only installation (P1)

- [ ] Close the three remaining whole-game record selectors: two Clips and one
      AssetBundle. The former 345-record frontier is closed except for these
      [three](PORTING_JOURNAL.md#j1347--reconstruct-whole-game-customrendertextures);
      provider additions through PR #324 do not prove a complete bundle.
- [ ] Assemble and qualify complete groups, bundles, scene/player/lab data and
      catalogs from public producers and legitimate current PC input. Historical
      readiness remains [693/705 available, 685 raw-exact](accepted-build-reconstruction.md);
      record closure and final-file readiness are separate checks.
- [ ] Qualify lighting numerically and visually against J850 and document the
      smallest practical tolerance in an ADR. The GPU floating-point/sampling
      tolerance class is decided; geometry-probe differences up to 134/255 remain
      unexplained ([local measurement](../work/coordination/p1-scenes-w/snowy-native-explicit-bake-v2/job.done.json)).
      Other asset classes remain raw-exact; report raw-exact, drift-explained and
      tolerance-accepted results separately.
- [ ] Complete on-phone production without Unity on the phone, retaining IL2CPP,
      original behaviour and authorized toolchain/distribution boundaries.
- [ ] Qualify fresh install, in-place update with the same on-device signing key,
      save retention and **Check for updates** against a public release. Installer
      UI/release fetch/session install and manifest/incremental rebuild/signing
      must pass together; partial host or installer tests do not close P1.

## Stability and performance

- [ ] Attribute remaining managed retention and demonstrate a plateau, then run a
      sustained session. Matched assisted-session growth fell from about 680 to
      [219 KB/session](PORTING_JOURNAL.md#j1350--restore-original-console-retention-default-at-composed-startup);
      the positive slope remains open. Use the
      [final-menu heap](PORTING_JOURNAL.md#j1353--capture-the-requested-final-menu-heap)
      for attribution rather than repeating the completed corrections.
- [ ] Close the [performance release gate](public-alpha.md#performance-release-gate):
      profile converter time/memory/heat/storage per stage and sustained gameplay
      FPS, frame pacing, battery and visual fidelity; optimize measured costs
      without changing bytes or original behaviour. Startup now requests
      [300 FPS](https://github.com/danielbuva/ror2-android-port/pull/322);
      sustained 60 FPS acceptance remains open.
- [ ] Complete physical controls, long-run dependency retention and remaining
      interrupted-write/ENOSPC/recovery cases in the [alpha checklist](public-alpha.md).
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

- [ ] Finish rebuild equivalence (`Hidden/Compositing`) and replace remaining local
      runtime-contract/shader/inherited-content/provenance inputs; switch the working
      build to the rebuild path ([migration plan](migration-removal-plan.md)).
- [ ] Check provenance drift after accepted baselines and replay R1–R8 when needed.
- [ ] Have `Start` call `GameSession` directly; reduce shared coordinator state.
- [ ] Replace historical timestamped input dependencies with named receipts or retire
      those actions; move still-needed gameplay drivers into tracked owners.
