# Capability gates

Canonical policy: DEVELOPMENT_PLAN.md. Each gate requires stored real-device evidence, not compilation alone. Shared procedure: preflight → minimal change/build → install/runtime-path discovery/sync/run → structured logs/crash/state plus relevant visual capture → first-failure classification → state/journal/commit. Query live storage on each install/size increase and retain prior APK/payload; never change storage or unrelated data.

| Gate | Status | Objective, scope and acceptance | Dependencies / principal risk |
| --- | --- | --- | --- |
| L0–L2 baseline | PASS, T01 reproduced | Accepted input; exact toolchain; original utility AOT, converted mesh on adopted data; GLES/Vulkan historical proof, fresh Vulkan capture | T01; not game readiness |
| L3 managed execution | PASS — full original DLL, ten assertions × three cold launches | Original RoR2 slice expected results, three cold launches ≥30 s; preserve API/type identity | T02/T05/T06/T07; AOT/middleware |
| L4 recovered scene | PASS — isolated content J28; diagnostic binding/material, original loader deferred | loadingbasic plus dependency-rich animated prefab on device; required GUID/local fileID/script/subasset/catalog audit | L3; serialization; T10 before large data |
| L5 lawful startup/menu | OPEN — J55 reaches Addressables; J61 blocks the current original Steam/platform route before ownership checks | Observed initialization, truthful services, optional no-audio lifecycle, Android profile/content roots, original menu navigation | L4/L9 foundation; entitlement/native lifecycle; ADR-001 review |
| L5.5 original simulation | OPEN | Original Commando master/body/authority/state ticks; deterministic movement then built-in controls; three cold launches ≥60 s | L5; see detailed plan; no complete stage needed |
| L6 controllable stage | OPEN | Introduce whole original stage to proven simulation; handheld movement, camera, aim, default abilities, collision/animation | L5.5; catalog/stage integration |
| L7 combat/complete stage | OPEN | Enemy/damage → pickup/interactable → director → teleporter; normal complete stage, readable G4 gameplay | L6; authority/effects/simulation |
| L8 complete offline victory | OPEN | Route transitions/lifetime/finale/victory/results/return menu/profile; normal uninterrupted victory then second stable run | L7/L9; late dependencies/memory |
| L9 profile | OPEN — J39/J57 isolate roots/config; real original save/cold reload unproven and Steam-backed profile flow blocked by J61 | Fresh Android-only foundation before L5; cold reload, interrupted write, update retention, backup/restore by L8 | Path audit; host Steam profile immutable; lawful platform/profile boundary |
| L10 audio | OPEN | Early lawful engine/bank/codec access; later init bank, SFX/music/spatial events/callbacks/shutdown | Authorized compatible engine; banks/authoring |
| L11 graphics | L11-a PASS J66: original Commando material assignment and bounded Vulkan albedo/emission; broader families open | Minimum surface/terrain/character/UI/hazard families with L4–L7; G5/G6 parity later | Required scene families; shaders/dummy export |
| L12 performance | OPEN | Warm stage/combat, transitions, memory and thermals; optimize measured bottleneck, stable 30 FPS first | Meaningful gameplay; final after L8 |
| L13 transformation | OPEN | Clean ignored regeneration/provenance/cache checks; same accepted input; real second-build compatibility when available | Stable route; update/toolchain |

Replan at L3, L4, L5.5, L6, L7, L8. No gate advances from a stripped empty build or synthetic completion. Audio/visual parity, broader routes/devices, T30/60 FPS, distribution and remote services remain later unless a measured dependency requires them.

## Evidence

T01: work/runs/20260913T020341.114229Z-46130c90d7a1, visible Vulkan geometry, utility marker, ARM64 IL2CPP, adopted placement and cleanup. Doctor/preflight and six host tests passed. LAST_KNOWN_GOOD_RUNTIME under work/checkpoints binds baseline APK and payload; no scene/simulation/playable/run pointer exists yet.

J62 architecture review retains C as platform-deferred. J63 completes L10-a read-only lifecycle attribution: the later native query/dialog, bank producer/callback lifetime, and platform-coupled teardown remain unproven, and no runtime candidate is selected. No milestone advances; L5, Steam-backed profile startup and L5.5 remain blocked. See architecture-review-j61.md and l10-a-unavailable-audio-lifecycle-audit.md.

J64: L11-a is selected for constructive device execution. Independent simulation precursors may be scoped before L5, but cannot pass formal L5.5. No milestone advances from this selection; see l11-commando-material-device-contract.md.

S01 / J68 independently verifies original EntityStateMachine queue, update/fixed scheduling, automatic ticks and cleanup on Android. It does not advance formal L5.5: actual character states, movement and authority remain unproven.

S02 / J69 verifies original CharacterDirection facing and its authority guard using a real local server-owned identity. Original movement, full character authority and L5.5 remain unproven.

S03–S06 / J70 pass independent input-edge/normalization and inactive motor output/acceleration tests in four fresh Android processes. No translation, collisions, normal body stat calculation or L5.5 acceptance is implied.

S07–S11 / J71 pass shipped kinematic solver integration, wall stop/slide, stable grounding and ungrounding in five separate Android processes. An authored diagnostic velocity controller drives these probes; original CharacterMotor/body integration and L5.5 remain unproven.

S12/S14 (J72) and S13 (J73) pass original CharacterMotor-driven movement/braking, Jump-method impulse integration without gravity, and wall contact. S15 fails in original OnLanded with a null-reference exception; landing and full character simulation remain open.

S16–S19 / J75–J77 establish bounded original landing context and resolve the J72 null-reference for this fixture. Diagnostic artifact catalog and inactive body/Run remain; fall damage, effects/audio, normal character initialization and L5.5 are not accepted.

S20–S24 / J78 pass original gravity and GenericCharacterMain input-driven movement/stop in isolated diagnostic fixtures. This is original state-to-motor execution, while full Commando/master lifecycle, normal stats/catalogs, physical controls and formal L5.5 remain open.

S25–S28 / J79 pass source-gravity motor jumping and original grounded state movement, reversal, stopping and wall contact (101 assertions). S26 accepted only after isolated same-APK retry following device disconnection. Diagnostic fixture scope remains; input-driven jump inventory/networking and full L5.5 remain open.

S29–S32 / J81–J82 pass recovered jump-item identity, empty original inventory lifecycle, server-only jump-event dispatch and original input-to-jump/landing (96 accepted assertions). Original movement-state execution now includes the first jump press. Full recovered Commando/master/body lifecycle, normal catalogs/stats, local-client delivery and physical controls still prevent L5.5 acceptance.

S33–S36 / J84 pass selective original setup on actual recovered CommandoBody and PlayerMaster, plus diagnostic buff storage and original registries. Prefab caches/relationships are proven, but these roots are inactive: complete Start/stat/body-master/client/controller simulation remains unproven. No formal L5.5 advancement.

S37–S40 / J85 pass original recovered state-machine network setup, actual server body/master spawning/authority and original master-ID recording/resolution. Inventory adoption and reciprocal linkage remain unproven; this does not advance formal L5.5 or establish a local client/player.

J87 adds bounded original inventory adoption to L5.5 prerequisites: five original definitions, actual master resolution, inventory identity and one original callback pass in two fresh Android launches. Inactive roots and subset catalogs remain. Normal stats, reciprocal linkage, local player/client and formal L5.5 remain open; L5 platform blocker unchanged.

J88–J90 add five separately accepted Android prerequisites: team experience, recovered team membership, minimal Run singleton lifecycle, default skill setup and motor capsule bounds. Original stat calculation still fails at the measured knockback BuffDef dependency; no stat or formal L5.5 acceptance. Three distinct failed attempts remain preserved.

J92 completes bounded S46 original level-one stat calculation after S49 buff storage and S50 zero-buff handler pass. Expected health/speed/damage/jump values and original completion event agree on Android. J91 malformed bundle/reference failure preserved; no formal L5.5 advancement or recovered character-motion claim.

J93 adds S52: recovered solver binding/authority and original motor acceleration/cap/braking using original calculated stats pass on Android. S51 level-up fails at original application/effect context, with missing Addressables runtime data; no level-two acceptance. Full recovered state/solver motion and formal L5.5 remain open.

J94 passes S53–S55 on Android: recovered named Body main-state entry/exit, original input gathering and state-driven free-space solver motion with computed stats. Motion reaches x5.844 after one simulated second and stops at x7 after neutral input. Inactive selective lifecycle, no gravity/collision or visual character-motion acceptance; formal L5.5 remains open.

J95/J96 pass S56–S58: recovered original motor Start/event, source-gravity free fall, and short-drop floor contact with original landing/server callbacks. Initial floor-overlap failure is preserved; corrected clearance yields one landing and stable grounding. Inactive explicitly stepped fixture, no material effects/audio or full L5.5 acceptance.

J97 passes S59–S61: recovered original grounded movement/stop, reversal and wall collision with original computed stats/capsule/source gravity. Three fresh Android processes pass; formal L5.5 remains open because simulation is explicitly stepped on inactive roots, without visual animated-character, reciprocal/client or physical-control acceptance.

J98 adds S62 visual agreement: recovered bind-pose display copies at original simulation start/stop positions produce the expected 512-pixel displacement under a fixed camera. Original grounded motion remains passing. This is two diagnostic captures, not animation, automatic lifecycle or controller acceptance; formal L5.5 remains open.

J99 passes S63 recovered jump prerequisites (actual sound/item/count/computed-stat context). S64/S65 fail because no local jump event is observed in the server-only recovered setup; no recovered jump acceptance. Effective movement authority differs from original HLAPI local event ownership. Real client/owner semantics must be tested next; formal L5.5 remains open.

J100 confirms recovered raw authority=false/effective=true with no client owner. J101 passes minimal original local connection/readiness and authority assignment/message delivery/removal with clean teardown. The earlier teardown-error runs remain rejected. Recovered-object client callbacks and jump acceptance are next; formal L5.5 remains open.

J102 observes recovered client ownership and original input-driven jump/landing, but rejects S69–S72 acceptance because readiness serialization lacks the active state catalog index and logs packet failure. No checkpoint advances. Entity-state catalog/serialization is the next bounded prerequisite; formal L5.5 remains open.

J103/J105 pass original bounded state-catalog serialization and recovered body initial serialization independently. Client readiness still fails; J104 identifies uninitialized master entitlement-tracker storage. Entitlement semantics must remain truthful during any lifecycle follow-up. Formal L5.5 remains open; no clean client/jump milestone advancement.

J106 passes recovered master initial serialization, local-client readiness, body authority, original jump-event delivery and input-driven jump/landing in five separate fresh launches. Original tracker allocation preserves the absent-user/empty diagnostic catalog state; no entitlement-service proof. Reciprocal master/body lifecycle, sustained simulation and physical controls remain open, so formal L5.5 does not advance.

J107–J109 pass untouched default master loadout serialization but find original reciprocal spawning blocked before server registration: the fresh inactive body lacks original Awake-populated team/skill caches. Lifecycle initialization is the next prerequisite. Prior client/jump checkpoints remain accepted; formal L5.5 remains open.

J111/J112 restore measured original CharacterMotor order and pass automatic root lifecycle plus original reciprocal master/body spawning and server registration. Children remain inactive; body is stopped before Start. Full startup/catalog lifecycle, sustained simulation and physical controls are still required for formal L5.5.

J113 passes original master body-start callback on the reciprocally spawned body: one event and health 110 with actual zero-count GummyCloneIdentifier context. Original body Start stops at its explicit BodyCatalog-index guard. Catalog registration/content behavior is next; formal L5.5 remains open.


J114 passes original bounded BodyCatalog registration on Android, including an honestly failed body-name portrait lookup and retention of the actual serialized icon. Catalog-assigned index/name/prefab identities agree after callbacks drain. Next integrate the registered prefab into S83 before original SpawnBody/Start; share bundle ownership and postpone catalog cleanup until clone destruction. This does not pass body Start or formal L5.5.


J115 exposes original indexed loadout defaults as the next dependency. J116 passes their original catalog/initializer path and diagnostic CharacterBody.Start on the original spawned inactive clone: body index 0, skin 0, health 110 and one master/body event each. Separate loadout/Start receipts retained (395/402 assertions). Automatic root Start, original SpawnTeleporterState→main progression, continuing simulation, spawned-body client integration and physical controls remain open; formal L5.5 does not advance.


J118 accepts original spawn state catalog/configuration and Weapon/Slide Idle Start/exit. J119 accepts the complete original hidden-buff removal/timed contract and original SpawnTeleporterState entry/exit on an inactive spawned body. Rejected attempts remain preserved. Original timed transition is still blocked at null teleport material; exact legacy GUID/type/asset locations are now verified for the next bounded provider experiment. No automatic or sustained simulation gate advances; formal L5.5 remains open.


J120 passes original teleport Material cold sync/async loading, overlay setup/update/explicit removal, and original SpawnTeleporterState→GenericCharacterMain progression. Separate receipts retained (416/428/430 assertions). Effect/audio are unavailable in this bounded mapping; exported shader is a dummy. Selected callbacks/fixed stepping on inactive roots do not establish automatic sustained simulation or formal L5.5.


J121 passes original motor Start, neutral main-state ticks and scripted input/motor/solver motion on the actual original SpawnBody clone after body Start and timed spawn progression. Original computed speed 7/acceleration 80 yield 5.844-unit movement and braking to rest at 7. Three separate receipts retained (434/435/437 assertions); inactive roots, explicit scheduling, zero gravity/no collisions remain diagnostic limitations. Automatic lifecycle/ticking, clone gravity/collisions, client ownership and physical controls remain open; formal L5.5 does not advance.

J123 passes automatic original spawned FSM callbacks and a separate original automatic motor-start/solver-registration neutral hold, each over 60 seconds. Body continuing callbacks and children remain inactive; body Start and overlay application updates are diagnostic. Automatic motion rejects before input at a final-frame overlay observation/ownership race; no motion or formal L5.5 acceptance. Correct that observer lifetime before motion retry; retain the two independent accepted receipts.

J124 passes S100 automatic original spawned FSM/motor/KCC motion and braking with a 60-second stable hold (3967 assertions). The final-frame overlay observation/ownership race is corrected without changing simulation. S98/S99/S100 are three independent accepted 60-second automatic component probes, with separate receipts and original DLLs unchanged. Full body callbacks, source gravity/collisions, live visuals and physical/client controls remain separate; formal L5.5 and L5 do not advance.

J125 passes four separate automatic source-gravity/landing/grounded-stop/wall probes, each with a 60-second hold (free-fall hold uses zero gravity after its measured pulse). Body continuing callbacks and Run clock remain unproven; introduce original body callbacks next with natural buff expiry/timer observations before broader lifecycle. Formal L5/L5.5 does not advance.

J126 passes actual original Unity CharacterBody Start/Update/FixedUpdate with natural spawn-buff expiry/stat recalculation/stationary timer, separately neutral and source-gravity grounded movement holds over 60 seconds. Body continues under original callbacks, but HealthComponent/skills/direction/children, original Run clock and physical/visual acceptance remain open. Formal L5.5 does not advance; next isolate original health fixed tick before combat.

J128 passes original automatic neutral HealthComponent fixed tick/regeneration accumulator with a 60-second hold; full-health-only, zero gravity/no collisions and inactive Run clock limits remain. J129 rejects barrier acceptance despite correct math because barrier-triggered original stat recalculation needs the absent original BarrierEffect prefab. Recover only that original-provider closure/lifecycle before retry; no error suppression or barrier checkpoint. Seven new independent automatic component probes S101–S107 accepted; formal L5/L5.5 does not advance.

J131 passes original barrier prefab loading/release only (S109); broad CharacterBody.Init still rejects on 21 missing effect locations (S110). Lifecycle/automatic barrier and formal gates remain open. Next isolate the original barrier completion callback against its actual successful handle; do not suppress failures or fabricate full Init readiness.

J133 passes original BarrierEffect lifecycle and natural automatic barrier decay/effect expiry, separately 487/4118 assertions. Original successful-handle completion is diagnostically invoked; broad Init still rejects on missing unrelated effects. One original shader-alpha material copy survives effect destruction and is explicitly released by owned cleanup. Sixty-second stable original body/health/FSM/motor/KCC hold passes with no new runtime errors. Run clock/other callbacks/children/physical controls/visuals and formal L5/L5.5 remain open; next inspect CharacterDirection before expanding root callbacks.


J135 passes S113–S116 original automatic CharacterDirection on the actual original SpawnBody clone: natural Start/Animator cache/authority/ModelBase identity, neutral hold, original input east turning/motion/braking, west reversal and public aim-timer turning/natural expiry. Four separate cold launches each hold over 60 seconds (7653/5792/5763/7596 assertions), original body/health/FSM/motor/KCC stable, owned cleanup and 45 unchanged DLLs; 21 host tests pass. Only known shader/layer messages, no new errors or matched crashes. Inactive model/children, zero gravity/no collisions, Run clock and diagnostic overlay/state teardown remain; physical controls/client ownership/live visuals/full Init and formal L5/L5.5 stay open. Next isolate original ModelLocator Start/detachment/LateUpdate follow and owned model destruction before expanding the visual hierarchy.


J138 passes S117–S120 original automatic ModelLocator: natural Start detaches the exact inactive original model from ModelBase; original LateUpdate follows neutral/movement/reversal/aim facing, and original OnDestroy destroys it before provider release. Four separate 60-second holds, 1803 pose samples each with zero errors, 13070/11208/11179/13012 assertions, 45 unchanged DLLs, 21 host tests; known shader/layer messages only, no new errors/crashes. J136 harness ordering failure preserved and corrected before retry. Inactive visual hierarchy, Run clock/zero gravity/no collision and diagnostic overlay/state teardown remain; animation/live visuals/controls/abilities/full Init and formal L5/L5.5 remain open. Next audit original GenericSkill/default SkillDef callbacks for isolated timing/recharge.
