# Execution backlog

Open work only. Completed and superseded T/S/I/C issue records are archived verbatim in
[history/execution-backlog-2026-10-16.md](history/execution-backlog-2026-10-16.md); full results
are in the [journal](PORTING_JOURNAL.md). Remove an item here when it is done and record the
result in the journal.

## Gameplay integration

- [ ] Unassisted full run with normal-difficulty combat (all current route evidence is assisted).
- [ ] Commit an actually earned alternate loadout choice through the profile (J493 revisit).
- [ ] Observe the remaining J503 achievement conditions (near-death charge, two-stack Mountain
      Shrine, loop) and positive ordinary unlock grants without assists.
- [ ] Complete default and alternate ability semantics for the base survivors.
      Callback coverage is broader than complete effects; continue with the exact
      live variant inventories and output owners (J673, J684, J685).
- [ ] Finish the opt-in source-stage lifecycle: observe natural teleporter/boss
      rewards and exit before extending transport and its table/identity turnover.
      Preserve the strict source retirement and effect-reference guards; current
      native UI-abandon/restart passes in J1045 (J726/J730 resolve J710).
- [ ] Identify the intermittent LightningStake nonfinite transition across projectile
      identity turnover; retain native elite behavior while collecting evidence (J667).
- [ ] Play the nine staged DLC scenes once a truthful expansion-availability path exists (J488).
- [ ] Resolve native Siren egg targeting/interaction after source entry and exact
      Listening registration (J812); validate boss start/defeat, rewards, disabled
      MapZones, exact egg retirement and stage teardown.
- [ ] Moon/finale/escape: manual sessions only, never navigated autonomously.

## Stability and performance

- [ ] Device-test J914's retained dependency ownership against J915's next-menu
      failure; measure the additional bundle retention and preserve ordinary
      survivor/profile/entitlement checks and source audio termination.
- [ ] Attribute the remaining ~52 MB/session managed growth (J787): not reachable
      from enumerable static/live roots; next a long session series on the
      internal Nova to test whether PSS or Boehm usage reaches a limit.
- [ ] Integrate original position indicators (`TeamComponent.Init`, player/NPC/boss
      indicator prefabs and Nameplate text), compared against PC captures (J787).
- [ ] Attribute the crowded-stage enumeration hot path from the app-scope trace
  (J761), then reduce measured frame time; 60 FPS is release acceptance.

## Structural cleanup

Order and rationale: [ARCHITECTURE.md](ARCHITECTURE.md#known-structural-debt).

Release prerequisites, deferred by operator decision (Phase 2 paused 2026-10-20, J766):

- [ ] `Hidden/Compositing`: R9 builds inside `-executeMethod -quit`, before the startup callback
      that records the shader (J766). Land `claude/r9-compositing-fix`, then prove it with a
      working-project build, both baseline checks and an R9 run.
- [ ] R7's runtime-contracts result: replace the editor export with a host producer (as J714 did
      for the catalog).
- [ ] The 46 shader recovery inputs (hash-pinned local analysis inputs).
- [ ] The 14 inherited-store files (12 need an exact-editor `RecoveredHudBuilder` step).
- [ ] The provenance map's role in selecting step membership.
- [ ] Switch the working project's own build to the rebuild path (migration-removal commit 9,
      [plan](migration-removal-plan.md)).

Open:

- [ ] Drift check after every few accepted baselines: refresh the provenance map from the working
      project (keep a backup), then replay R1–R8 from a clean checkout of the accepted commit
      (host only, about 25 min, J750).
- [ ] Have `Start` call `GameSession` directly instead of selecting the session by id.
- [ ] Replace the hard-coded run folders in historical actions with named receipts, or retire
      those actions. The input-update optional-guard dependency now uses an explicit
      hash-pinned named receipt; scene preparation/audio/teleport dependencies remain.
