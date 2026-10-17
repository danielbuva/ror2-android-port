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
- [ ] Play the nine staged DLC scenes once a truthful expansion-availability path exists (J488).
- [ ] Moon/finale/escape: manual sessions only, never navigated autonomously.

## Stability and performance

- [ ] Attribute managed-memory growth across repeated sessions.
- [ ] Crowded later-stage frame time (main thread over budget); 60 FPS is release acceptance.

## Structural cleanup

Order and rationale: [ARCHITECTURE.md](ARCHITECTURE.md#known-structural-debt).

- [ ] Delete the build's dormant exact-text C# patches (`whole_catalog.py:1074`, `:1075`, `:1111`); the authored sources already contain that code (prerequisite for C# formatting).
- [ ] Split `MovementBatchProbe.Result` into session config and report.
- [ ] Give the shipped game its own entry point instead of an experiment-switch case.
- [ ] One runtime source manifest instead of "already present in the generated project".
- [ ] Remove the rebuild blockers listed in [LOCAL_STATE.md](LOCAL_STATE.md), including the
      untracked device runner scripts.
- [ ] Register `./dev` actions as current or historical.
