# Execution backlog

Open work only. Completed and superseded T/S/I/C issue records are archived verbatim in
[history/execution-backlog-2026-10-16.md](history/execution-backlog-2026-10-16.md); full results
are in the [journal](PORTING_JOURNAL.md). Remove an item here when it is done and record the
result in the journal.

## Gameplay integration

- [ ] Compare the opt-in source view against a matched PC reference and resolve
      measured color/lighting differences; terrain visibility is restored in J1077.
- [ ] Complete audio mix/spatial/event-attribution/audibility acceptance; source
      stage clients and bounded release/restart are qualified in J1080.
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
      native UI-abandon/defeat and restart pass in J1045/J1046 (J726/J730 resolve J710).
- [ ] Identify the intermittent LightningStake nonfinite transition across projectile
      identity turnover; retain native elite behavior while collecting evidence (J667).
- [ ] Play the nine staged DLC scenes once a truthful expansion-availability path exists (J488).
- [ ] Repair J1105’s charged-teleporter navigation stall on Scorched Acres;
      preserve original movement/out-of-bounds semantics before repeating the Siren route.
- [ ] Resolve native Siren egg targeting/interaction after source entry and exact
      Listening registration (J812); validate boss start/defeat, rewards, disabled
      MapZones, exact egg retirement and stage teardown.
- [ ] Moon/finale/escape: manual sessions only, never navigated autonomously.

## Stability and performance

- [ ] Qualify J914's retained dependencies over a long repeated-session series
      while preserving ordinary survivor/profile/entitlement checks. The native
      menu/restart boundary now has J1045/J1046
      and [J1066](history/journal-J1-J1177/PORTING_JOURNAL.md#j1066--qualify-native-settings-feedback-and-two-step-end-run-controls)
      device coverage; original Term/disarm and bounded application-owned Quit pass
      in J1077. Long-run retention remains open.
- [ ] Bound corrected repeated-session managed usage and PSS over a completed
      internal-device series, then qualify a sustained session. J1086 supplies
      the completed uncorrected measurement;
      [J1091](history/journal-J1-J1177/PORTING_JOURNAL.md#j1091--qualify-native-heap-capture-and-identify-retained-laboratory-log-payloads)
      attributes captured retention to diagnostic JSON and returned bullet hits.
      [J1092](history/journal-J1-J1177/PORTING_JOURNAL.md#j1092--correct-captured-retention-producers-and-preserve-a-failed-commando-series)
      builds and installs the corrections; preserve its zero-session failure.
      [J1100](history/journal-J1-J1177/PORTING_JOURNAL.md#j1100--complete-twelve-corrected-commando-sessions-and-retain-a-smaller-growth-frontier)
      completes all 12 corrected Commando sessions with no runtime errors, but
      the consistent menu samples retain 0.579 MiB/session positive growth.
      Attribute that smaller frontier with a separate native heap pair before
      claiming a full bound; retain the post-collection spike in the evidence.
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
