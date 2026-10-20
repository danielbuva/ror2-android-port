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
- [ ] Finish the opt-in source-stage lifecycle: validate native source rewards and
      completed-session identity/table teardown before extending transport. Resolve
      J710's effect-reference attribution using J716's operation witness; retain
      exact source-table restoration and generated identity-binding checks.
- [ ] Identify the intermittent LightningStake nonfinite transition across projectile
      identity turnover; retain native elite behavior while collecting evidence (J667).
- [ ] Play the nine staged DLC scenes once a truthful expansion-availability path exists (J488).
- [ ] Complete Siren's source controller/toggle/spawn lifecycle and exact egg
      retirement ownership before native listener registration (J723), then validate
      boss start/defeat, rewards, disabled MapZones and stage teardown.
- [ ] Moon/finale/escape: manual sessions only, never navigated autonomously.

## Stability and performance

- [ ] Attribute managed-memory growth across repeated sessions.
- [ ] Attribute the crowded-stage enumeration hot path from the app-scope trace
  (J761), then reduce measured frame time; 60 FPS is release acceptance.

## Structural cleanup

Order and rationale: [ARCHITECTURE.md](ARCHITECTURE.md#known-structural-debt).

- [ ] Make R9 equivalent (J586): resolve the `BlueNoise_R8_1.png.meta` working-project drift
      (J592) and find why `Hidden/Compositing` drops out of R9's APK (a second build in the same
      Library still omits it, J598; next: a Library-less build of a working-project clone).
- [ ] Remove the rebuild's remaining local inputs (R2's migration evidence is gone, J597):
      the 47 hash-pinned analysis inputs (R3's ten are regenerated on the host since J725; left:
      R7's runtime contracts, an editor export, and 46 shader recovery inputs),
      the 14 inherited-store files (12 need an exact-editor `RecoveredHudBuilder` step) and the
      provenance map's role in selecting step membership.
- [ ] Switch the working project's own build to the rebuild path (migration-removal commit 9,
      [plan](migration-removal-plan.md)).
- [ ] Have `Start` call `GameSession` directly instead of selecting the session by id.
- [ ] Replace the hard-coded run folders in historical actions with named receipts, or retire
      those actions.
