# Official Rewired trial reference comparison

The official Unity-2021 trial is **1.1.65.3.U2021**, while this game ships **1.1.47.0.U2021**. The current trial is not a drop-in replacement. This experiment imports it exclusively into an ignored, isolated exact-editor reference project. The accepted laboratory project and original DLLs remain intact.

## Provenance and scope

The user obtained `Rewired_U2021_Trial.zip` from the [official trial form](https://guavaman.com/projects/rewired/trial). The package, license, complete archive/file inventories, hashes, project, input data, logs and generated outputs stay under `work/experiments/rewired-trial/20261003T223818.072258Z`. Its five-minute runtime restriction remains intact; the physical observation is bounded to 90 seconds. Trial software and generated proprietary data are not published.

The trial comparison uses the supplied source, public/protected reflection and Unity serialization APIs. It does not decompile or inspect trial IL, protected resources or enforcement code. Read-only metadata inspection of the legitimate original input establishes the other side of the comparison.

Prior art: `community-prior-art.md` distinguishes disputed AOT slots from a working Android input backend. Pinned Starstorm2 `BorgMain` consumes the original inputBank and base state lifecycle; it supplies no Android backend workaround. The vendor's [installation instructions](https://guavaman.com/projects/rewired/docs/Installation.html) specify installer-managed input axes and early execution order. Its [troubleshooting guidance](https://guavaman.com/projects/rewired/docs/Troubleshooting.html) separates controller detection, player assignment, maps and actual input observations. Those boundaries govern this probe.

## Measured compatibility

The original inventory scans all 143 assemblies. RoR2 is the sole game consumer: 172 Rewired member references and 48 type references. The trial matches 170 public/protected signatures. Matching signatures do not establish behavioral or binary compatibility.

| Contract | Original input | Current trial / consequence |
|---|---|---|
| Keyboard naming | `GetKeyName(UnityEngine.KeyCode)` | Overload absent; current overloads use `Rewired.KeyboardKeyCode`. An unchanged original call cannot resolve. |
| UI input inheritance | `RoR2.UI.MPInputModule` derives from a nonsealed `RewiredStandaloneInputModule` with public constructor | Trial class is sealed and has a private constructor. The original derived type cannot be preserved against it. |
| UI type assembly | `Rewired_CSharp` | Supplied scripts compile into `Assembly-CSharp`; ten otherwise matching consumed members change assembly scope. |
| Core assembly name/version | `Rewired_Core`, assembly version `1.0.0.0` | Same assembly version despite different product version and bytes. It is not a compatibility discriminator. |
| Mouse-source interface | Two original game implementers of `IMouseInputSource` | Consumed interface members and parent interfaces have no measured additions/removals. Full runtime semantics remain unproven. |
| Input data | Three player definitions (System 9999999, PlayerMain 8, Player2 10), 44 actions, two map categories, two joystick layouts, 26 joystick maps, two keyboard maps, one mouse map | Passive import retains all row identities and original map contents. Original Android settings remain present. |
| Configuration evolution | Original schema | Trial adds 167 default fields and drops three Xbox One/Stadia settings. Float32 and packed-array representation differences are accounted for separately. Empty conflict arrays deserialize as empty arrays. |
| Controller registry | 166 hardware maps and six templates | 187 hardware maps and six templates. Registry equality and all controller behaviors are not claimed. |
| Serialized script binding | Original compiled script and registry identities | A copied passive prefab explicitly rebinds the manager to trial source and its registry to trial data. The original unresolved optional Switch component remains visible as one missing script in that passive copy. |

The original installation and archived 45-DLL accepted set remain unchanged. No current Android DLL is mixed with the old core merely because its assembly name matches. A matching older authorized package is preferable for preserving the measured contracts. Any current-package adaptation needs a separately specified API, inheritance, assembly/serialization and behavior candidate.

## Installer and build evidence

The official package contains 520 asset paths, including `Rewired_Android.dll` and supplied Android platform/JNI branches. Imported plugin metadata enables the Android assembly; its legacy CPU label alone does not establish ARM64 execution.

After the vendor installer completes, the original 18 reference-project input axes remain an unchanged prefix of 512 axes: 494 entries are added. The manager execution order is `-32000`. File hashes distinguish package import, installer edits and authored probe additions.

The first scheduled build never starts: a pending inspector `delayCall` is measured while the editor is idle. It is cancelled before the dispatcher changes to a one-shot editor update, with start and terminal receipts. The first actual build AOT-compiles but fails Gradle signing because the reference restart omitted the established isolated Android/Gradle homes (the previously documented J86 issue). Its failed receipt and logs remain preserved. Restarting only the reference editor with those existing homes produces the same SDK-only Vulkan ARM64 APK with **zero errors**, in 14.65 seconds of cached retry. Compilation is not controller acceptance.

## Bounded physical probe

`./dev prototype --action rewired-trial-inventory` records the comparison. `./dev prototype --action rewired-trial-run` requires that comparison, a successful terminal build, the actual owned lab package ID, the configured Nova and a recoverable previous APK. It uses the existing install/storage/ownership safeguards and restores the prior APK afterward, then sleeps Nova.

The reference scene creates one trial manager and copies its observed game input data. It does not instantiate the passive copy's unresolved Switch component. It contains no RoR2 assemblies, application initialization, platform services or character simulation. The SDK probe records readiness, controller count, original player/action identities, loaded map categories, raw joystick axes/buttons and mapped game action values. Human-labelled controls are required before accepting a physical mapping.

The first device launch rejects an empty reference manager: the authored serialized-property iterator never enters its root. The corrected builder enters once, copies top-level fields, and checks action count plus registry identity before building. An accidental duplicate authored script copy then causes a compiler rejection and is archived before removal. The subsequent corrected APK initializes ReInput and all 44 actions, but the probe rejects PlayerMain ID 0 against an incorrect expectation of 8.

Exact original source resolves this: the core constructs runtime System at 9999999 and other players by ordinal (0/1), separately from serialized definition IDs (8/10); RoR2 calls `GetPlayer(0)`. The observer expectation changes to the measured original runtime contract. No input data is renumbered. Both failed device attempts, their APKs, reports and rollbacks remain preserved.

The successful build enables this observation. It does not advance original ReInput/controller capability, L5 or formal L5.5. A result must distinguish SDK backend operation, data compatibility and original game integration.


## Device result and decision

S129 completes one reviewed **90.001-second SDK-only Vulkan ARM64 observation**, with 264 events, one joystick, all 44 original action identities, original runtime players 9999999/0/1 and both gameplay/UI categories. Six default maps are present and enabled. Evidence: `work/experiments/rewired-trial/20261003T223818.072258Z/device/20261003T233119.293641Z`; accepted APK SHA-256 `c11d6609db9245db720de060df169afd849989ecf5c1a1923da0102088428974`. This is a reference observation, not an original game input checkpoint.

| Physical control | Trial observation through copied game maps |
|---|---|
| Left/right sticks | Signed raw X/Y and MoveHorizontal/MoveVertical or AimHorizontalStick/AimVerticalStick values |
| L2 / R2 | Raw trigger 0→1→0 and SecondarySkill / PrimarySkill values |
| L1 / R1 | UtilitySkill / SpecialSkill button edges |
| A / B / X / Y, Xbox physical order | Raw A/B/X/Y; Jump/UISubmit, UICancel, Interact, Equipment outputs as applicable |
| Start / Select | Raw Menu / View; Start/Pause / Info |
| L3 / R3 | Raw Left/Right Stick Button; Sprint / Ping |
| D-pad | Four distinct raw directions and mapped UI/action outputs |
| M1 / M2 | No distinct raw trial events; extra-button exposure is not accepted |

The user confirms completion with L3/R3 performed at the end, matching recorded timing. The reviewed screen reports completed observation and 264 events. No current-PID Unity errors, crash entries matching the process, or exception records since launch appear. Retained exception/crash files contain historical entries and are not attributed to this run. Installation and runtime data use the live adopted backing; the prior owned APK is restored at its original hash. Nova is verified asleep afterward; Thor is untouched. All 45 original DLL hashes still match both accepted archived stages. Thirty-five host tests pass, including package/terminal-build rejection, current-process SDK first-failure capture, failed capture cleanup and rollback after a post-install verification failure.

**Decision:** the official trial does provide a functioning Android input path on this device, and this copied action/map closure produces meaningful input. It does not establish a compatible replacement for the original 1.1.47 binaries. No trial Android DLL is mixed with the old core, and no original game controller or L5.5 capability advances.

Before integrating, obtain a vendor-authorized matching 1.1.47 Unity-2021 package if available and compare its actual core/Android/binding contract. A current licensed package must be inventoried independently; this trial's findings do not prove that licensed bytes or APIs are identical. If only a newer package is available, specify a separate bounded compatibility candidate for the measured keyboard call, UI inheritance/constructor, assembly/script identities and original game-facing player/map initialization. Preserve action/player/map definitions and the accepted original rollback. Successful SDK input alone cannot select that transformation. Trial timeout remains intact; continued reliance and distribution require appropriate licensed access.
