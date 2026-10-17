# Baseline checkpoint

The known-good state every cleanup or feature step is compared against. Update it only
when a new APK passes `./dev check-baseline` and its journal entry is written.

## Standard check

`./dev check-baseline` (`scripts/lab/baseline.py`) runs on the installed APK. It selects
Commando from the ordinary offline menu, with invincibility as the only (diagnostic)
assist, so no permanent progression is granted. It stops at 35 s of live world play or as
soon as the run leaves the first stage, and it always force-stops the app and turns the
display off. It passes when:

- the run reaches 35 s of `integrated-world-playing` on Lakes;
- the session report has no `error` or `firstFailure`;
- the run is marked assisted;
- the profile's applied-run count is the same at the end as at the start of world play.

Evidence goes to `work/experiments/baseline/<timestamp>/` (`result.json`, final report,
log and screenshot). It needs the configured device and the payload already synced.

## Current baseline (2026-10-17)

| Item | Value |
| --- | --- |
| APK | `e504e79891be4d1644c6f54f37334641e226f11ba83f2277e51c1e1d0a04e400`, built in J516 from `main` with the boundary-file headers |
| Check | passed: 35.2 s on Lakes, no report error, 13 applied profile runs unchanged (J516) |
| Earlier evidence | J503 achievements and J504 survivor/stage breadth ran on `f567e9f6…`, which has the same runtime code |
| Rollbacks | J503 `f567e9f6…`, J502 `39538592…`, J425 `5a25bb9f…`, J323 paused Moon `893b03c4…` (full hashes in [PORTING_STATE.md](../PORTING_STATE.md)) |
| Placement | adopted storage, updated in place |

Not covered by the check: other survivors, stage transitions, ordinary (unassisted)
difficulty, audio, frame rate and visual parity. Use the journal entries above for those.
