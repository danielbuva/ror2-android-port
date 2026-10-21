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
- teardown verifies selector absence, process exit and the selected device's
  configured idle display policy.

Evidence goes to `work/experiments/baseline/<timestamp>/` (`result.json`, final report,
log and screenshot). It needs the configured device and the payload already synced.
It binds the installed ownership receipt's APK even when this worktree has no
local build pointer; `is_current_build` is false in that case.

Before any runtime write, a checked directory listing must positively show that
the diagnostic selector is absent. Transport errors and incomplete listings
refuse. Live process checks distinguish a successful `pidof` no-match from
command/transport failure; report-file absence, a partial JSON write and a failed
read are separate states. A final report must belong to the launched process.

Teardown attempts selector removal, force-stop and display sleep even after a
failed push or another operation. Removal and process exit are checked again;
unknown or failed teardown cannot return success. The result's `cleanup` object
records selector/process absence and whether display sleep was requested and
verified. If both the operation and teardown fail, the error retains both.

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
modes have device evidence (J663). It does not assert a particular commerce purchase count
or ordinary-difficulty acceptance.

Stage mode freezes its final evidence at the last current-process report and force-stops
the app before artifact collection, so collection cannot prolong the run. Its screenshot
is therefore taken after the app stops. Both modes remove the selector, force-stop and
turn the display off in `finally`, including if collection fails. Stage-mode results add
`mode`, `transitions`, `scene` and `stage_world_seconds` to the usual evidence receipt.
The plain check and its acceptance criteria remain unchanged.

## Current baseline (2026-10-20)

J926's later diagnostic APK ac1d2176 is installed after both standard checks
and an independent final installed/cleanup query. It remains unpromoted while
selected-camera rendering and original-audio playback acceptance are open.
See the [current snapshot](../PORTING_STATE.md) for installed identity and
[J926](PORTING_JOURNAL.md#j926--build-r22-and-observe-selected-music-context-through-both-standard-checks)
for the single result record. The accepted baseline below remains the rollback.

| Item | Value |
| --- | --- |
| APK | `f1550ce0ff030ea0fa7a1ab66de19d54ee7894a7ae2f5b344f993157d6713949`, source 1780ea9; 111 runtime sources, 312 frozen authored inputs, 266 payload hashes unchanged, matching symbols and same-request pre-strip capture |
| Check | Both modes pass on the adopted-storage gameplay device with no report/current-process failure or applied-run change: 35.206436 s on Lakes and one exit plus 10.111176 s on Goolake. Both record current-build true and stable owned artifact identity. Full evidence is recorded once in J850. |
| Placement | Adopted Nova updates in place with fresh adopted-only placement checks. Thor retains the earlier J818 automatic-check result on APK 107718f8…; this new APK was not installed there. Current assignments reserve adopted Nova for gameplay/audio, internal Nova for the separate alpha session, and Thor as an unassigned spare. |
| Rollbacks | Previous baseline J840 `8357db8b…` and all retained executable rollback hashes are listed in [PORTING_STATE.md](../PORTING_STATE.md). |

J850 qualifies J847/J848 on the default route only. The opt-in native skin lifecycle
and Siren recorder still require explicit targeted runs. J814 separately passes a stock MUL-T
four-callback retry without reproducing the earlier NRE, and a Commando
loss/restart observer lifecycle. The NRE cause, MUL-T teardown, native Huntress
target updates/Siren execution, indicator rendering/teardown and special
first-stage recovery remain open; the default checks do not qualify them. J801's observer and strict cleanup failures remain
evidence on that player. J790's earlier native
offhand activation and J795's bounded native Siren registration/cleanup remain
evidence on their recorded APKs. [J898](PORTING_JOURNAL.md#j898--observe-siren-registration-and-five-ordered-navigation-pairs-without-a-boss-start)
records the later bounded fae79734 Siren observation; encounter execution remains open.

The default checks keep native diagnostic flags off. Native first-stage defeat,
strict cleanup and healthy same-process restart previously pass on J752's APK
in J753. Native stage transport, ordinary-difficulty acceptance, complete skill
semantics, audio, sustained frame rate and PC visual parity remain separate
gates; their current status and evidence links are in
[PORTING_STATE.md](../PORTING_STATE.md).
