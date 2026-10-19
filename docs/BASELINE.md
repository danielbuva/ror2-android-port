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

## One-exit subsystem check

`./dev check-baseline --stage-exit` is the second standard mode, for stage transport,
the teleporter and the longer commerce/shopping path. It keeps ordinary Commando
selection and the same first-stage seed, with invincibility, high damage and fast
charge enabled as diagnostic assists. Movement and jump boosts stay off; no permanent
progression is granted. It never selects a destination, Moon or a finale, and does not
enable the Gold Shores route.

The existing bring-up auto-input drives combat, earned-money purchases, navigation and
interaction with the original teleporter. The host only taps Start at the report's
`hud.menuStartX`/`menuStartY` coordinates. This follows the ignored local
`run-huntress-premoon-j504.py` runner and the J504 survivor-breadth runner under
`work/experiments/whole-catalog/gameplay/`; neither sends a teleporter tap. J504's
[journal entry](PORTING_JOURNAL.md#j504--broaden-original-survivor-execution-without-changing-the-apk)
records the assisted multi-stage evidence. In the authored runtime,
`IntegratedWorldStimulus` invokes `ObjectiveWorldStimulus`, which navigates and presses
interact when the original selector targets the idle or charged teleporter.
`TransportIntegratedStage` verifies original boss defeat, charge and exit completion
before incrementing the transition count. No teleport, charge or commerce mechanism
is reconstructed by this check. The pinned R2API.Director source discussed in
[community prior art](community-prior-art.md#future-subsystem-map) separates stage and
interactable population from completion; catalog presence alone is not an exit proof.

It passes only when:

- `stageProgress.transitions` is exactly 1;
- `stage.scene` is nonempty and differs from Lakes, with phase
  `integrated-world-playing` and no transport in progress;
- `world.seconds - stageProgress.enteredAt` is at least 10 s (both runtime timings
  must be present and valid), following the Huntress runner's stage-age calculation;
- `error` and `firstFailure` are empty, the run is marked assisted, and the profile's
  `appliedRuns` matches the first live Lakes report.

The host polls every 2 s and stops at the first qualifying report. Before transition 1,
any reported nonempty scene other than Lakes outside an active transport stops
and fails immediately. A second exit request, transport after transition 1 or a transition
count above 1 also stops and fails. Invalid transition counts, report errors, process
exit, ordinary results or the 370 s host deadline fail. The check never intentionally
drives another exit.
This is a host polling guard, not a new runtime transition interlock. Both baseline
modes have device evidence (J604). It does not assert a particular commerce purchase count
or ordinary-difficulty acceptance.

Stage mode freezes its final evidence at the last current-process report and force-stops
the app before artifact collection, so collection cannot prolong the run. Its screenshot
is therefore taken after the app stops. Both modes remove the selector, force-stop and
turn the display off in `finally`, including if collection fails. Stage-mode results add
`mode`, `transitions`, `scene` and `stage_world_seconds` to the usual evidence receipt.
The plain check and its acceptance criteria remain unchanged.

## Current baseline (2026-10-19)

| Item | Value |
| --- | --- |
| APK | `76344ab433b15b97943638a5807227278f07cf98a18ef372873988d57c945ebe`, J604 native teardown/auxiliary-observer code build, retaining the J585 layered reimport and whole Timeline pin |
| Check | passed: 35.21 s on Lakes and one genuine stage exit to Goolake with 10.09 s next-stage play, no report error (J604) |
| Earlier evidence | J503 achievements and J504 survivor/stage breadth ran on `f567e9f6…`; the current runtime additions need their own acceptance |
| Rollbacks | J585 `da5e4959…`, J503 `f567e9f6…`, J502 `39538592…`, J425 `5a25bb9f…`, J323 paused Moon `893b03c4…` (full hashes in [PORTING_STATE.md](../PORTING_STATE.md)) |
| Placement | adopted storage, updated in place |

The one-exit mode adds one assisted transport/teleporter exit, and the current baseline
passed it (J604). Neither mode covers other survivors, ordinary (unassisted) difficulty,
audio, frame rate or visual parity. Use the journal entries above for broader existing
evidence.
