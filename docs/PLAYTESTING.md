# Owner-build playtest checklist

Current scope: the prepared laboratory desktop fallback. Phone-only builds,
fresh public-input bootstrap and final player installation remain open. Keep all
owner-generated APKs/payloads and raw evidence private. Read the
[player guide](PLAYER_GUIDE.md), [alpha policy](ALPHA_POLICY.md),
[screen inventory](SCREEN_COVERAGE.md) and [current status](../PORTING_STATE.md).
A prepared-lab result does not close the fresh-owner gate.

## Prepare and install a matching build

Set `PLAYTEST_DEVICE` to the explicitly authorized, allowlisted serial. In a
shared worker session, acquire its local device lease before any ADB command.
Use only the assigned device. Run from the checkout with the owned local receipt
and configuration; never borrow another device receipt or guess a storage path.

1. Configure the external legitimate PC installation and pinned toolchain as in
   [DEVELOPING.md](DEVELOPING.md#local-setup). Keep the original unchanged. Run
   input inventory/diff review and explicit acceptance; refuse unknown, changed
   or incomplete versions. The first alpha selects local files only and defers
   account downloads and Steam Cloud.
2. Commit the source, run host preflight, then build through the shared Unity
   mutex. A linked worktree can use `shared-catalog-code-build`; add `--full` for
   content or runtime-membership changes. Keep at least 100 GB free on the host.
   The ordinary primary checkout actions remain current.
3. Record the build receipt's source commit, accepted input, exact toolchain,
   request, APK SHA-256 and complete matching payload manifest. Preserve the
   last known-good compatible set by path/hash; use APFS clones only when an
   independent artifact is required for shared-build coordination.
4. Set `PLAYTEST_APK` and `PLAYTEST_PAYLOAD` to that exact pair and run:

```sh
: "${PLAYTEST_DEVICE:?Set the authorized device}"
: "${PLAYTEST_APK:?Set the matching APK}"
: "${PLAYTEST_PAYLOAD:?Set the matching payload}"
./dev doctor --device "$PLAYTEST_DEVICE"
./dev storage --device "$PLAYTEST_DEVICE"
./dev preflight --device "$PLAYTEST_DEVICE"
./dev install --device "$PLAYTEST_DEVICE" --apk "$PLAYTEST_APK"
./dev sync-data --device "$PLAYTEST_DEVICE" --payload-dir "$PLAYTEST_PAYLOAD"
```

Resolve the first actual failure. Doctor may distinguish a missing historical
smoke receipt from a current input/editor/device failure; do not invent a passing
smoke. Read the fresh install and sync receipts: package bytes, placement and
runtime-data backing are separate observations. Refuse foreign ownership,
capacity, signature or payload mismatches. Preserve other games/data and storage
configuration. No uninstall, forced downgrade or data clear is a recovery step.

## Run the two assisted controls

```sh
./dev check-baseline --device "$PLAYTEST_DEVICE"
./dev check-baseline --device "$PLAYTEST_DEVICE" --stage-exit
```

Read `is_current_build`, the actual installed APK hash, current-process logs,
profile observations and terminal selector/process/display checks. A missing or
different local build pointer may honestly record `false`; never rewrite it to
claim a different artifact was tested. Keep failed attempts. See
[BASELINE.md](BASELINE.md). Assisted controls do not qualify ordinary player input,
a normal run or a memory bound.

## Ordinary controls and session case

Record start/end times, artifact identity, selected survivor/difficulty and every
assistance setting. Use actual physical presses for controller qualification.
ADB/synthetic events, automatic diagnostics and host fixtures are distinct
supporting evidence. Thor has a separate ordinary touch route; its physical
controller mapping remains unqualified. The scoped software motion case does
not qualify the physical touchscreen digitizer.

| Case | Required observation |
| --- | --- |
| Physical movement/camera | Both sticks, neutral/held state, original movement/aim consumers, deadzone and invert/sensitivity; no diagnostic producer |
| Skills and interaction | Jump, all four skills, equipment and interaction through native consumers; normal cooldown/release, no assistance |
| Touch | Movement and aim together, skills/equipment/interaction, menus and cancellation; simultaneous pointers and pointer loss release held actions |
| Mappings/rebinding | Explicit measured device identity; bind/save/cold-load; disconnect/reconnect and neutral reacquisition; do not copy Nova mappings to Thor |
| Menus/settings | Survivor/difficulty/loadout availability remains profile/entitlement filtered; touch/controller focus and cold preference persistence |
| Pause/focus | Pause freezes native clock/fixed ticks, releases held actions, and resumes only the owned pause; background/return keeps the same live session or honestly reports loss |
| End run | Open confirmation, cancel without teardown, reopen and confirm; no completed result/reward is fabricated; owned native teardown reaches menu |
| Second session | Start through the menu in the same process; no stale world/input/listener ownership, profile change or runtime error |
| Genuine loss/results | Natural defeat, native result/ledger persistence exactly once, results navigation and ready same-process restart |

The [screen inventory](SCREEN_COVERAGE.md) identifies absent original screens.
Touch gestures feed the existing native input bank and camera adapter. Keep
acquired-equipment/interaction effects and genuine play separate from a bank-edge
witness or an empty-slot request. Keep Moon/finale manual. Coordinate rendering/audio/animation and an unassisted normal run with the
main gameplay owner; a nonzero audio meter or loaded bundle is insufficient.

## Stability, persistence and updates

- Observe a long repeated-session series only after each session passes teardown.
  Record post-collection managed usage, PSS, live completed owners, object/bundle
  counts and process lifetime. A completed series with a positive memory slope
  leaves attribution/bounding open; record the measured limit rather than
  extrapolating indefinite stability.
- Separately record sustained frame time, thermals and background/resume under a
  matched workload. Identify the hardware and conditions in private evidence;
  a short assisted run is not a supported-device performance guarantee.
- Qualify abrupt process death/crash recovery and ANR handling. Verify actual
  next-launch profile/settings/ledger validity and absence of duplicate results;
  an intentionally killed process alone does not reproduce an ANR.
- For interrupted writes and storage refusals, preserve the owned prior files,
  prove invalid pending data is never adopted, and exercise validated-backup
  recovery. Never fill unrelated storage, alter its configuration or remove
  another app's data to create a test condition. Report the exact injected
  condition separately from a real interruption/storage failure.
- Update only with the same owner signing identity and a greater version code.
  Check profile/settings before update, after install and after cold restart.
  Rollback rebuilds compatible prior source with a greater code and the same
  owner key. Public alpha identity/signing and actual game update/rollback remain
  unqualified until their own evidence exists; fixture retention is separate.

## Review feedback and finish

Settings feedback provides a notes draft, an exact fixed-field preview, sharing
consent, clipboard copy and a tokenless GitHub browser draft. Review every field.
Manual notes are not automatically redacted. No raw log, screenshot or attachment
is collected. Opening the browser may send the preview text to GitHub; submitting
an issue is a separate action. Add an attachment only after reviewing it and
explicitly selecting it yourself. Do not attach game files/generated packages,
account/session details, private paths, device/storage IDs or signing data.

The separate [baseline feedback preview](BASELINE_FEEDBACK.md) selects typed
facts from a standard check for manual review. It does not scrub arbitrary logs.
Keep the private APK receipt and raw failed-run evidence locally. Record results
once in the journal, refresh its index and replace the current state snapshot.

Run `python3 scripts/prune-generated.py --apply` after build/run tasks and before
finishing. Verify the owned selector is absent, the lab process is stopped and
all configured physical displays are asleep; then release the device lease.
