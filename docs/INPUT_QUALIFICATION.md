# Physical input and rebinding qualification

This is a design and acceptance contract. Current-alpha physical controls,
physical touch and user rebinding remain open. Host fixtures below do not
qualify hardware, original Rewired integration or ordinary play. The current
release gates live in [public alpha](public-alpha.md); the prepared-lab procedure
lives in [PLAYTESTING](PLAYTESTING.md).

## Existing ownership and evidence

`InputSessionPolicy` in `NovaInputBoundary.cs` selects the existing measured Nova
route, touch-only Thor route or explicit automatic diagnostic route. Unknown
models refuse. `NovaInputSession` reads the private attempt-bound mapping,
validates it before assigning it to `NovaInputBridge`, and owns teardown.
`NovaInputBridge` samples the measured Unity joystick slot, translates axes and
buttons into the original `InputBankTest`, and neutralizes on pause, focus loss,
disable or controller loss. Original gameplay remains the consumer.
`NovaThirdPersonView` owns camera conversion. `AndroidTouchInput` owns pointer
captures; active touch takes the manual gesture. `AndroidOfflineSettings` owns
deadzone, look sensitivity and invert-Y preferences; it does not store bindings.
The [architecture](ARCHITECTURE.md#ownership) remains the owner map.

Historical evidence must retain its scope:

| Evidence | What it establishes | What it leaves open |
| --- | --- | --- |
| J143/J144 | Human-labelled Nova kernel events | Unity indices, action binding and gameplay |
| J145 | Original Rewired Windows backend mismatch | An Android backend for that original middleware |
| J149 | Separate official trial's physical action exposure | Drop-in compatibility, original game integration |
| J150/J151/J152 | Corrected Unity exposure and physical Nova movement/aim/jump on the historical spawned-body fixture | Current-alpha full action coverage and remapping |
| J156 | Historical integrated physical controls and original primary execution | Current-alpha controller/menu/kit acceptance |
| J757 | Explicit diagnostic mode without measured Thor input | Thor hardware mapping |
| J1071/J1091 | Software touch/native-consumer and lifecycle evidence | Physical digitizer, hardware controls and remapping |

Full results remain in the [journal](PORTING_JOURNAL.md), searchable through its
[index](JOURNAL_INDEX.md); [the bridge notes](nova-input-bridge.md) describe the
historical removable adapter. A capture's completion, kernel label or joystick
name alone is insufficient to accept a physical mapping. J144 specifically
shows why physical face-button position must be labelled by the human rather
than inferred from kernel names. The J345 restored-mapping finding also makes
mapping provenance a prerequisite before attributing a downstream failure to
input.

Prior-art review: the input section of [community prior art](community-prior-art.md)
preserves action/player/map identity. The pinned Starstorm2
[`BorgMain.cs`](https://github.com/TeamMoonstorm/Starstorm2/blob/a9a4baddc5dd4405e893ab5dfc684eb9e27c26f8/SS2-Project/Assets/Starstorm2/Modules/EntityStates/Cyborg/BorgMain.cs)
retains base jump/fixed-update lifecycle and observes input-bank/authority state.
That source informs observation at the bank and native consumer; it supplies no
Android controller backend. The source was inspected at that pin. No community
or original game implementation is copied into the fixtures. Passed original
Rewired contracts and package pins stay unchanged.

## Mapping contract today

The private `nova-input-mapping.json` is a lab measurement artifact, not a
portable controller profile. The production `Mapping.Validate(expectedAttempt)`
requires exact attempt equality and a nonempty observation reference, four
distinct axes in `[0, 15]`, five distinct buttons in `[0, 19]`, and vertical signs
of exactly `-1` or `1`. Enabled interaction requires a sixth distinct in-range
button. Disabled interaction may retain an unused index. Validation checks the
supplied value without assigning it or changing defaults.

The host `nova_bridge.bind` owner additionally admits only a successful complete
current-attempt raw report, confines its reference to that attempt, checks
bidirectional mapped-axis excursions and observed mapped-button presses, and
records the observation hash. Runtime validation alone does not verify the
observation file/hash or prove a physical correspondence. Session setup
separately refuses `enableSkills`; the bridge's existing session/diagnostic flags
control native skill delivery. Shape validation must never be reported as skill
execution acceptance.

| Physical input destination | Existing mapping or owner | Remaining acceptance |
| --- | --- | --- |
| Move and look | `moveX/moveY`, `aimX/aimY`, vertical signs; camera owner | Physical directions, sign, range, drift and camera behavior on the candidate |
| Jump | `jump`; render-to-fixed latch | Short press, hold, release, landing and cancellation |
| Four skills | `primary/secondary/utility/special`; session delivery flags | Each native equipped action, cooldown and release on the candidate |
| Interact | Optional `interact/enableInteraction` | Native target selection and genuine interaction effect |
| Equipment, sprint, pause/menu and UI navigation | No physical fields in this mapping | Measure and specify before adding bindings; touch support does not qualify them |

Connection admission requires the same measured joystick name in slot 1, no
other nonempty joystick slots, and a stable neutral interval of 0.25 s after
suspension. All twenty sampled buttons participate in the neutral check, even
when unbound. This is a narrow measured-device rule, not a controller discovery
or hotplug support promise.

The source now makes `NeutralSample` use the same radial conversion as `Stick`
for both mapped sticks. Previously, separate component checks could admit a
diagonal whose components were each below the threshold even though its radial
magnitude produced movement. The host regression fixture first rejects that
behavior, then passes with the shared criterion, including centered, cardinal
edge, diagonal edge and just-outside samples. This is host-only source
qualification: no new APK or device reconnection acceptance follows. Default
bindings, configured deadzone and the 0.25 s interval remain unchanged. Physical
reconnect evidence on the resulting candidate remains required.

## Smallest rebinding implementation

Extend the existing paused settings surface and bridge/session owners. Do not
add gameplay execution to the mapping screen or replace the middleware. The
first useful scope is rebinding the existing measured button fields on an
already qualified controller. Axis selection, new device discovery and new
physical actions remain separate work until measured.

1. Pause through the existing native pause owner and call bridge neutralization.
   Edit a separate candidate value; never expose the active mapping's mutable
   object as the draft. Show measured physical positions and action names.
2. Capture one press followed by release after the controller is neutral. Require
   a human-confirmed physical label against the current raw observation. Do not
   map the press used to open the screen, guess face names, or silently swap an
   occupied binding. A collision keeps the draft and displays the conflicting
   action; the user chooses another button or cancels.
3. Validate the complete candidate against the current measured attempt before
   saving. Keep the existing observation relationship and delivery restrictions.
   Validation failure leaves the accepted mapping untouched. Do not convert this
   attempt-bound artifact into a durable cross-device profile by changing its
   attempt field alone.
4. Reuse the settings store's validated pending/readback/backup transaction policy
   in the existing mapping owner. Save failure keeps the paused draft with a
   retry; Cancel discards it. Do not claim a saved mapping until its persisted
   value has been read back and validated. Do not add bindings to preference
   JSON without an explicit persistence design and fixtures.
5. Activate the saved candidate at the next gameplay-session setup, using the
   existing validate-before-assignment path. The initial feature need not hot
   swap a live bank. End the old input owner normally, clear pending actions,
   and require release plus the stable neutral interval before the new session
   accepts physical input. Cancel and save failure retain the previous accepted
   mapping. Interrupted-save/restart recovery must select a complete validated
   value, never a partially edited draft.

This sequence keeps the first implementation small while giving Apply, Cancel,
Retry and restart concrete behavior. It requires host fixtures for capture
release/collision, draft isolation, failed-save recovery and next-session
activation before shipping. The paused settings modal now implements this button-only sequence through
`NovaInputBridge.ButtonRebind` and `MappingStore`. Menu/back stays reserved;
collisions name their action. Same-attempt saves preserve observation hash and
accepted-mapping provenance. Capture, filesystem recovery and modal routing have
host fixtures; physical labels/effects, Android save interruption and restart
without host resync remain unqualified. The active session never swaps maps.

## Physical acceptance on the candidate

Use an explicitly authorized device and the existing device-cycle safeguards.
Record the actual installed APK hash, input receipt and mapping observation
reference before starting. Keep raw identifiers, captures and screenshots local.
Arrange the human-labelled test window before waking the display; unattended
diagnostic input cannot satisfy these cases.

| Case | Required evidence |
| --- | --- |
| Labelled exposure | Human moves each stick both ways, releases it, and presses/releases each selected button separately; compare actual Unity exposure with the labels |
| Movement and camera | Ordinary manual mode, each direction and diagonal, center/stop, low travel, full travel and look inversion/sensitivity; observe original bank plus actual native movement/camera |
| Native actions | Short tap and hold/release for jump and each eligible equipped skill; real interaction/equipment effect when their physical paths exist; bank state alone is insufficient |
| Simultaneous controls | Move, look and an action together; no lost release, duplicate jump edge or unintended UI click; test touch-to-controller handoff separately |
| Pause/focus | Pause or background while holding movement and actions, then return while still held; no gameplay action until the required release/neutral reacquisition |
| Disconnect/reconnect | Suspend/neutralize, reject wrong or ambiguous controller, reconnect the measured controller while held, then release for the stable interval; include a diagonal near the deadzone |
| Rebinding, once implemented | Cancel preserves the active map; collision does not change it; save/retry/restart selects the verified value; the old button ceases its action and the new one causes exactly that native action |
| Cleanup | End session, verify native input release and no retained capture owner, restore display configuration and sleep idle OLED panels |

Classify the first failed boundary as exposure, mapping admission, producer,
bank delivery, native consumer, UI routing or persistence. Preserve the failed
attempt and avoid retuning a map to conceal a consumer failure. Journal a
completed experiment once with its APK hash, actual physical method, exclusions
and revisit conditions. Advance only the capability actually observed; a
historical Nova pass cannot qualify a new device or a current-alpha build.

## Host fixtures

`tests/test_nova_input_mapping.py` extracts the production mapping, raw sample,
presence and stick/neutral methods and compiles them against the pinned Unity
2021.3.45f2 managed API. `tests/fixtures/NovaInputMappingHost.cs` supplies only
authored values. Its cases cover provenance rejection, range/collision/sign
validation, optional interaction, nonmutating validation, radial conversion and
all-button/mapped-axis neutral reacquisition, including the radial regression.
They also cover opening-press exclusion, press/release, collisions, ambiguous
chords, disconnect, draft isolation, provenance-preserving save/reload, pending
rejection, backup recovery and failed-write retry with a controlled JSON peer.
No raw device input, middleware or
game implementation is embedded. Missing pinned Mono/Roslyn skips the fixture.

Run the focused fixture with:

```sh
python3 -m unittest discover -s tests -p test_nova_input_mapping.py -v
```

Existing `test_nova_input_presence.py`, `test_android_touch_input.py` and
`test_portable_diagnostic_input.py` cover presence transitions, pointer ownership
and source-selection guards. These fixtures do not exercise Android input
dispatch, a physical digitizer/controller, native gameplay effects or the
rebinding screen on Android.
