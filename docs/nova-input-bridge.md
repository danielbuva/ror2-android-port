# Temporary Nova input bridge

User-directed path after the isolated Rewired trial: defer exact middleware integration and translate Nova physical input into original `InputBankTest`. The original Rewired assemblies, serialized contracts, state machines, movement, motor, solver and skills remain unchanged. This proves only the configured Nova and one Unity joystick in slot1.

Prior art: pinned Starstorm2 `BorgMain` at a9a4badd consumes inputBank and calls original GenericCharacterMain ProcessJump/FixedUpdate. It supplies no Android controller backend. The measured original PlayerCharacterMasterController produces move/aim/button fields; GenericCharacterMain consumes them. Own NovaInputBridge writes those fields before original fixed ticks, retains jump button edges across render/fixed timing, and neutralizes input on focus loss, pause or disable.

The complete labelled Unity capture uses corrected axis serialization and live34-entry verification. Original18 entries remain; sixteen diagnostic slot1 axes are added locally. User confirms the sequence. Mapping:

| Physical control | Unity legacy exposure | Temporary consumer |
| --- | --- | --- |
| Left stick | axes0/1; Y sign-1 | planar moveVector and raw directional states |
| Right stick | axes2/3; Y sign-1 | normalized planar aimDirection |
| A | button0 | jump |
| B / X / Y | buttons1/2/3 | B unused; X/Y reserved for skill1/2 |
| LB / RB | buttons4/5 | reserved skill3/4 |
| LT / RT | buttons6/7 and axes11/12 | recorded; unused in this movement proof |
| L3 / R3 | buttons8/9 | recorded; unused in this proof |

Radial stick dead zone0.18; fixed diagnostic camera uses world X/Z. Skill writes remain disabled until a separate ability-execution experiment. These bindings are temporary and do not claim the original Rewired action map. Ignore M1/M2.

The simulation fixture uses actual original CharacterMaster.SpawnBody, reciprocal body/master linkage, local server effective authority, original computed Commando stats, automatically ticked GenericCharacterMain/CharacterMotor/shipped solver and original ModelLocator. Its minimal original item subset includes empty-inventory GummyCloneIdentifier, JumpBoost and JumpDamageStrike requirements. Diagnostic floor, camera and aim stance are explicit. Original model behaviours remain inactive; a renderer-only recovered bind-pose copy displays the pose followed by original ModelLocator. Animation, original camera, stage, combat, menu, authenticated platform services and formal L5.5 remain separate.

The server-only fixture has effective authority and no raw client authority. Original jump code increments motor.jumpCount and broadcasts its RPC; local onJump runs only with client authority or an actual RPC receiver. Observe original jump-count increase/reset, input edges, height/velocity and landing rather than expecting that local callback.

Commands use existing build/install/payload safeguards and separate process evidence:

```sh
./dev doctor
./dev prototype --action nova-bridge-prepare
./dev editor --target lab --action character-motor-order
./dev preflight
./dev build --target vulkan --force
./dev prototype --action nova-bridge-raw-run
# After reviewing labelled capture, prepare ignored work/config/nova-input-mapping.json.
./dev prototype --action nova-bridge-bind
./dev prototype --action nova-bridge-commando-run
```

Preparation writes motor-order request200 from actual original metadata, plus own producer order-20000. After a helper repair, refresh before invoking that menu command. Physical dispatch rejects missing/stale order receipts or an unfinished build. `nova-bridge-raw-retry` retains a separate run after an attributed correction. Mapping push requires a completed current-attempt exposure, observed bidirectional axes and buttons, the owned lab package and its established app-data root. Raw reports, generated settings, APK/payload and profiles stay ignored. Screenshots and current-process errors are mandatory; the intentional Windows shader rejection is identified separately. Nova sleeps at command completion.

Restore the saved InputManager and archive the stage to remove the probe. Accepted APK/payload receipts retain rollback; failed runs never advance capability pointers. See journal J150/J151 for rejected setup/capture/observer attempts and subsequent acceptance notes.

Accepted S130/S131 evidence: J152,90.03-second simulation/121.19-second fresh Nova launch,43.53m planar movement/stop, physical aim consumed by original main state, one original jump-count increase/3.6375m rise/landing/reset. User confirms controls;14019 assertions,45 unchanged original DLL hashes,40 host tests, current-process logs/captures and original cleanup pass. Owned APK/payload remain installed; Nova asleep. Scoped rollback LAST_KNOWN_GOOD_NOVA_INPUT_BRIDGE retains complete local provenance. Formal L5/L5.5 and ability execution remain open.
