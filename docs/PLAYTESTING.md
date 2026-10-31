# Owner-build playtest checklist

Current scope: the prepared laboratory desktop fallback. Phone-only builds,
fresh public-input bootstrap and final player installation remain open. Keep all
owner-generated APKs/payloads and raw evidence private. Read the
[player guide](PLAYER_GUIDE.md), [alpha policy](ALPHA_POLICY.md),
[screen inventory](SCREEN_COVERAGE.md) and [current status](../PORTING_STATE.md).
A prepared-lab result does not close the fresh-owner gate.
[J1071](history/journal-J1-J1177/PORTING_JOURNAL.md#j1071--qualify-software-touch-native-pause-and-recovery)
records matching artifact/install receipts, both assisted controls, strict native
restart, a complete software-touch transaction and bounded recovery cases.
Hardware controls and fresh public-input installation remain unqualified.

## Prepare and install a matching build

Set `PLAYTEST_DEVICE` to the explicitly authorized, allowlisted serial. In a
shared worker session, acquire its local device lease before any ADB command.
Use only the assigned device. Run from the checkout with the owned local receipt
and configuration; never borrow another device receipt or guess a storage path.
All test panels are OLED. Keep them asleep between tests. Thor tests require
the top display only: verify physical `Built-in Screen ON` / `Screen-2 OFF`
throughout the run and restore the original vendor mode during teardown.
`Device.display` refuses a black overlay or a transient lower-panel OFF state;
do not bypass a refusal to continue a playtest.

1. Configure the external legitimate PC installation and pinned toolchain as in
   [DEVELOPING.md](DEVELOPING.md#local-setup). Keep the original unchanged. Run
   input inventory/diff review and explicit acceptance; refuse unknown, changed
   or incomplete versions. The first alpha selects local files only and defers
   account downloads and Steam Cloud.
2. Commit the source, then use an [isolated build lane](build-lanes.md) for
   parallel worker builds. Its preflight and editor operations retain the lane's
   mutex; creation briefly acquires the canonical mutex. Start with the cheapest
   applicable normal code/full build, keeping HEAD fixed during each operation.
   Use only the published APK/payload paths for installation, then remove the
   lane when done. Keep at least 100 GB free on the host. Ordinary primary
   checkout actions remain current for its owner.
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
Use the [input qualification contract](INPUT_QUALIFICATION.md) for measured
mapping provenance, the remaining rebinding implementation and physical cases.
The host radial-neutral regression fixture does not qualify reconnect behavior
on an installed candidate.

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
  Read the consistent `managed_before_presentation_bytes` menu slope alongside
  the immediate post-collection slope. Retain every spike; a negative regression
  dominated by an early spike does not establish a retained-memory bound.
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

For a prepared owned lab installation, bind diagnostics to the actual installed
APK SHA-256 from its verified receipt. Individual checks require their own shared
device lease, verifying idle teardown before releasing it:

```sh
: "${PLAYTEST_APK_SHA256:?Set the verified installed APK SHA-256}"
./dev prototype --action session-memory-check --device "$PLAYTEST_DEVICE" \
  --expected-apk-sha256 "$PLAYTEST_APK_SHA256" --sessions 12
./dev prototype --action settings-write-interrupt-check --device "$PLAYTEST_DEVICE" \
  --expected-apk-sha256 "$PLAYTEST_APK_SHA256"
```

The memory case selects Commando explicitly, leaves all five gameplay assists
off, uses diagnostic automatic input and requires strict cleanup for every
completed session. A runtime error stops the case; incomplete series and old
archived reports do not establish a growth bound. Native heap captures are a
separate opt-in attribution case and must not be mixed with this measurement.
[J1122](history/journal-J1-J1177/PORTING_JOURNAL.md#j1122--prepare-alpha-host-contracts-and-identify-an-old-heap-fingerprint)
records an old-heap graph fingerprint, without identifying the corrected retained
root. A fresh matched heap pair must inspect
actual GC/static roots and native bridges; stable native object counts alone do
not establish a managed-memory bound.

The combined batch supervises temperature zones independently, targeting 250 ms
samples and refusing gaps above 1 s. Abort when one CPU/GPU zone remains above
95 C for at least three seconds, with no sampling gap above one second.
A reading at or below 95 C resets that zone's continuity. Abort immediately
for battery at or above 43 C. Skin temperature and HAL status remain metrics.
Record sampled time above 80 C, CPU/GPU peak and phase; demanding moments at
80–85 C do not fail a run. Retain failed cases without automatic retry.
Before each stage, cool readable CPU/GPU/battery/skin zones to at most 50 C
with the OLED asleep, and battery back to at most 35 C before every stage.
At level >= 80%, confirm actual charging only after three consecutive positive
`current_now` samples 10 seconds apart; a nonpositive sample permits the usual
cool admission checks. Status 2 with zero current is admitted. Refuse confirmed
charging or level > 85%; report without retry and never change charging settings. Record
battery temperature, level and status in the trace and stage receipts.
Record other physical zones, including power-management,
charger and USB sensors, as excluded from admission only; continue sampling
them in raw observations and all-zone peaks. Admission follows
[J1148](history/journal-J1-J1177/PORTING_JOURNAL.md#j1148--restrict-gameplay-admission-to-cpu-gpu-battery-and-skin).
Record unreadable temperature interfaces as exclusions
with their type/path; they do not establish cool or absent sensors. Admission
readings at or below -30 C are also unavailable: record their type/path/raw value
and exclude them. A previously valid zone becoming a sentinel during gameplay
still aborts. Missing readable CPU coverage, other invalid numeric readings,
malformed readings, ADB failure or failed supervision also abort. Exact known
electrical pseudo-zones are excluded. The sentinel policy and host fixtures are
recorded in [J1141](history/journal-J1-J1177/PORTING_JOURNAL.md#j1141--exclude-unavailable-admission-thermal-sentinels).
Record CPU and all-zone peaks and retain runtime or unexpected errors as first
failures, following
[J1131](history/journal-J1-J1177/PORTING_JOURNAL.md#j1131--supervise-all-readable-gameplay-thermal-zones).
Admission discovery uses a separate 10-second timeout while idle; gameplay
reads the discovered physical temperature paths in one batch with the strict
runtime timeout and gap bound ([J1137](history/journal-J1-J1177/PORTING_JOURNAL.md#j1137--separate-thermal-admission-discovery-from-runtime-sampling)).
Completed stages checkpoint within one three-hour deadline; cooldown never
counts as play. The 70/55 C pause/resume rule applies to pausable tool jobs,
not gameplay. Battery/HAL checks remain additional limits.
J1127 records the superseded 70 C rule stopping cold startup at 72 C before menu
readiness, with a maximum sample gap of 0.737 s and Android force-stop evidence.
No stage completed; that observation does not establish sustained acceptance.

For an explicitly scheduled combined case, `alpha-stability-batch` owns **one**
canonical lease across the SDK interruption case, three-session heap pair and
30-minute assisted first-stage observation. Do not wrap it in another lease.
It requires an idle owned installation, an explicit verified APK digest, host
and device storage reserves (including 4 GiB capture headroom above 15 GiB free)
and a new absolute done-file under canonical ignored
`work/`. Schedule it only after the device owner reports safe handoff; a device
reboot/emergency state requires explicit clearance first. Launch once detached:

```sh
: "${PLAYTEST_DONE:?Set a new absolute JSON path under canonical work/}"
nohup ./dev prototype --action alpha-stability-batch \
  --device "$PLAYTEST_DEVICE" --expected-apk-sha256 "$PLAYTEST_APK_SHA256" \
  --done-file "$PLAYTEST_DONE" >"${PLAYTEST_DONE%.json}.driver.txt" 2>&1 &
```

The long-lived driver records its own PID in the lease, stops on the first
failure and publishes the done receipt after terminal verification and pruning.
Read that receipt after completion rather than polling the device. A failed
terminal readback preserves the lease and evidence for diagnosis. The sustained
case uses invincibility only, manual neutral input and small software camera
drags, fresh advancing JSON and battery/HAL stop limits. It requires native
End Run and restoration of every assist. It does not qualify ordinary play,
physical input, thermal performance across a full run or a memory bound. Keep
native-heap pause/allocation effects separate from repeated-session measurement.

The settings case observes a native pending-file creation and terminates only
the bound writer from its own Development-package UID, preserving the existing
preference values. It requires standard debug `run-as` access; ordinary package
stop remains failure teardown. It accepts recovery
only after proving that the old primary and an actual uncommitted pending file
survived, including a hash-verified private copy of the initial primary. The
SDK actor has a bounded lifetime independent of Android observer threads;
failure output is retained. A completed save or missed interruption window
fails the case. This
diagnostic does not qualify power loss, ENOSPC or a physical touchscreen.

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
