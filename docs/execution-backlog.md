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
- [ ] Complete skill kits for the base survivors beyond 35 s Lakes play (J504).
      Build and device-check J587's drafted skill accounting/loadout rows after the
      parallel editor/device lock clears; then use the tracked survivor check.
- [ ] Play the nine staged DLC scenes once a truthful expansion-availability path exists (J488).
- [ ] Validate the drafted Siren encounter owner: native eggs, boss start/defeat,
      rewards, disabled MapZones and stage teardown after the coordination lock clears.
- [ ] Moon/finale/escape: manual sessions only, never navigated autonomously.

## Stability and performance

- [ ] Attribute managed-memory growth across repeated sessions.
- [ ] Crowded later-stage frame time (main thread over budget); 60 FPS is release acceptance.

## Structural cleanup

Order and rationale: [ARCHITECTURE.md](ARCHITECTURE.md#known-structural-debt).

- [ ] Make R9 equivalent (J583): rerun R9 with the layered reimport (J585) and the
      `Unity.Timeline` pin (J584); find why `Hidden/Compositing` drops out; decide how R9 treats `Lab.unity` and export-form importers.
- [ ] Remove the rebuild's remaining local inputs: R2's migration evidence (B1, B3–B6, B8),
      the 63 hash-pinned analysis inputs and the 14 inherited-store files.
- [ ] Switch the working project's own build to the rebuild path (migration-removal commit 9,
      [plan](migration-removal-plan.md)).
- [ ] Have `Start` call `GameSession` directly instead of selecting the session by id.
- [ ] Replace the hard-coded run folders in historical actions with named receipts, or retire
      those actions.
