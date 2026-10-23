# Porting state

Last updated 2026-10-23 UTC after **J1022/J1024/J1026 (device)/J1025 (owner-build research)**.
R34 diagnostic 098646f6 passes both standard modes and strict current-process
log qualification. Its MainOutput request retains ready camera/context,
native network-sound mapping and all three original highlight assignments.
The bounded native callback reports finite nonzero samples; natural Term,
persisted waveform readback and composed audio remain unqualified. J1026's
combined source-view/PCM test reaches world play but stops because the visual
diagnostic defers the audio-only camera context; the next test uses the existing
default selection. Its retained source-view log also has unresolved Blit pass
errors. R33's separate source-view attempt reaches no report before its startup
deadline; its subsequent default-menu Quit passes without query timeouts. Loader's four
callbacks remain observed on R33, with full ability semantics and the separate
blue-elite event open. Main is stopped/asleep with 13 applied runs. First-sample
JSON and rendered parity remain open. Accepted rollback stays J850 f1550ce0.
This page is the current snapshot only: replace its
content on every update. Results are recorded once in the
[journal](docs/PORTING_JOURNAL.md) (searchable through the
[journal index](docs/JOURNAL_INDEX.md)); the previous long-form state is archived in
[docs/history/porting-state-2026-10-16.md](docs/history/porting-state-2026-10-16.md).

## Snapshot

| Item | Value |
| --- | --- |
| Accepted input | Steam build 25475991, input id `6af7ed94619fe1b4346974b4486afa03a8d1625a7820e92da0ff74d57208fe88` |
| Toolchain | Unity 2021.3.45f2 (88f88f591b2e), IL2CPP ARM64, Vulkan (`environment/toolchain.json`) |
| Owner-build research | [J984](docs/PORTING_JOURNAL.md#j984--generate-the-owner-assembly-prefix-without-a-project-oracle) qualifies the isolated 49-DLL/importer prefix from reviewed inputs and public recipes; a complete project remains open. J899/J902/J905/J920/J921 connect the authored phone compile/strip/convert/native/package/load chain. J931/J934 qualify static manager bindings and Android feature declarations. J939 target-key/API lookup equivalence remains failed. J948 qualifies static record-copy/insertion/consumer field alignment on Android. Node selection, container semantics, constructor results, populated maps, live target/module/state decisions, native usage and independent roots remain unqualified. J929 app hosting still fails its writable-execution refusal. Game compilation, content/shaders, permitted tool delivery and matched performance remain open. [J1020](docs/PORTING_JOURNAL.md#j1020--test-deferred-serialized-object-reads-on-android) matches all initial-file payload digests with deferred reads, but bounded 5/6/7 GiB imports still terminate before bundle return. [J1023](docs/PORTING_JOURNAL.md#j1023--qualify-an-authored-android-nativeaot-build-tool-fixture) qualifies an authored NativeAOT build-tool graph; the stock exporter stops at its unavailable Bionic ASP.NET runtime pack. Complete export remains open. [J1025](docs/PORTING_JOURNAL.md#j1025--run-the-pinned-importer-through-an-android-nativeaot-console) passes a separate importer console's authored two-asset control on Android; complete input/export and capacity remain open. Route A and the desktop fallback stay fixed. |
| Latest device-verified APK | J1022 diagnostic `098646f6cc931c2a8d01d91fe4dfdcf5f54c58d9fc6ad01137695992e58588bd`, source 5724dd7: full catalog/player build, fresh conversion proof, both strict standard controls and independent terminal readback. MainOutput callback samples are finite and nonzero; natural Term/readback and audio/visual acceptance remain open. Accepted J850 stays `f1550ce0ff030ea0fa7a1ab66de19d54ee7894a7ae2f5b344f993157d6713949`, source 1780ea9. |
| Installed now | Main has J1022 diagnostic 098646f6 in adopted storage. Installed bytes, owned placement, selector/process absence, display sleep and 13 applied runs are independently verified after both controls and the J1026 failure cleanup. Other devices remain outside this assignment. |
| Runtime source since verified APK | R34 recompiles the existing generated audio request pin for MainOutput; authored runtime owners, native library and transform recipes are unchanged from R33. No later runtime change is integrated. J1010's JSON proposal remains unintegrated; targeted persistence and rendering work remain open. |
| Previous diagnostic rollback | J1017/R33 `197101a8f5e511334ac577b77b09f2295df59559eb9467bc80941b204f8c3fc3`, source edb120f, retains both strict controls; J1024 records its separate failed source-view startup and passing default-menu Quit. J1013/R32 `4b1a7969d75238c647147956a3a32e160ba14fbed9f62751cb53edf5b99e1135`, source 8c526ed, retains both controls with the strict highlight null-prefab failure. J1006/R31 `88ecfc8cad36b9ee5c2bfa9b027047fae4a48ea0969ed8179e99aca4dfd0da15`, source 289f377, retains both controls with failed camera admission. J1000/R30 `bda75e3708b8f6dfa94d89e9cf07821d775375da3934d6702f7a74c9ccce62e0`, source b11893d, retains both standard controls. J979/R27 `213228ad3b6b70505f49c9002e08f841d254a5c2bf4cc075e0c78fb968fb0c2e`, source 2f81ab1, retains both controls and the J981 failed target route. J954/R26 `6dc44d98af45ebf262a2fdaea0251879f39c6ab0c066c423b5e1559cc2efc79d`, source bc8296a, retains J959/J962 PCM salvage and cold-persistence evidence. |
| Device tooling | J755 verifies discovery, allowlist/profiles, separate ownership/runtime receipts, fresh reserves and idle screens on all three. The secondary test device passes both checks and produces J761's app-scope trace. The spare test device passes J762's automatic game checks and isolated audio; generic physical input remains unverified. Unity builds serialize while selected-device runs overlap. J888 verifies checked observations and teardown in both alpha standard modes. |
| Executable rollbacks | J840 `8357db8b6ef29f8958c5f4207ad2207f214ee60ae4923cc68f6de55fe55f6770` · J828 `922cfb86e895118285d8c93f588ff57c4052154d15e88688bf7b46f357474112` · J817 `107718f8e318a22a90623ef3895c85ecdd164f4a5f8b3226dd342aaeec9113cb` · J813 `91b0b7c93e03772d5eafb26e059a3f942be7f28563d2a07b98607f43710c7e50` · J809 `4c37596cd5828047a5cb19bc2df8c5c6913333cce01104d3f0b1e4bf748dccb9` · J805 `66c8162dbdc97b86486b7a748b3da26887cf7399571a4724d31704b9c4ca8e66` · J801 `319a39871c3bcf43760b0d2a96a9634d859149699da1c2ca0c9944c40bc881e3` · J797 `40299fc59da8d6553bbd6681a4515ad4281b4ef6bcd33ac75012dce3c7a952b1` · J793 `23916334f598f68b2f3b7e464b709a74c0b54bb222107031d32dbac9f0a18494` · J790 `01654e8187c378e6b26dd6033aa2fac9ce6b7d1b140cb98bf8a0619ea50bf63c` · J788 `be26c21c4cd8ff15a8a663528216cf7a69394a51d8b9441a63a1a496f83e98b5` · J783 `1311f1057275ef2a34a3fc964a6f79e033086243d066deea40775b9178d2bba5` · J776 `bbd1f3c15958ee42d272d58770a8caa2a73e327354bc668d9564bbd595656eb9` · J771 `0dd3f57328883d9dd927362775277b876cbf59ddaa17e0a9d0e719a15094684d` (exact debugging symbols retained) · J767 `2aa936c059331c6a2dcf2a3ef56ef928103707b1f009532dbfaa1c6f6c9697c3` · J764 `d7974718a48c008d83ab0bb411a8ea22093cbc23950a76e7cfffa17297285bfa` · J762 `96006814dd2ba80f65cd24413c50c11c3061060f9d90977296f1e00d71ec7fd1` · J758 `aabf41ab5ece8a34d9ac4b70946dad5d8b827baa40e4dd927afd98e6ff15deee` · J752 `aa732f88948062c43a59378bf7dd53f1a473c828a479adbaee32e976207fb159` · J749 `771fc75282b45197d0dd25d3d537a121112ca35830c8d4dd516711aa7aa813cf` · J745 `caeeb62fe45e7b8bad8a89272390a11a392152b975277660675a75e56a230453` · J737 `12d793593d216ea50d6db400fb4e8f7a3258657acd39a382181f0dc6b18035f8` · J728 `885ea2946869ca8a206739cf74acd9bbf75705651d5f3974c30a56724d93e715` · J724 `b32998b87706977e2945ae3b709e26486b76bf9403894262877a9e3829d80b54` · J707 `d545d80048fbc26b882ada5ecb1e38346239f121d8cdb00266ef3d29be703bee` · J702 `efb0ba9354923c1fbe453d28364018e078627cd15c65fc4813dcc3f0c13d577d` · J698 `fe4dc0de0f70ec70b699e9d54e55e3e657c0a89f1f9efb52ee58411ed0bcc383` · J695 `039bc73d59822801da9258a7f90b5bfa7e77080e0c4d49058f81916a61f0cfbc` · J689 `55dee31826b7ecd545488d601490ba92623d6640a711e9a534fdd2c898ede861` · J680 `e09920fd9df2c5b03416b33766fbdaf4c64f2feeeee9b68eff200435c0716ebc` · J670 `ad84d0cb55bc6a18dabf67e90839c78100abcb846c6feaff13c758a6b8a6fb69` · J663 `6506b99bfa5004960721868b222d15010718a81f4c55f28bd29d153976d97cec` · J657 `86d2542aadcc12dbfdb53fe957d7aedf32ebeb8d38c94fbf4732ef5211ed7d03` · J654 `f57e172b9da1a5717144355266cd2e1a1de93fa775c14233a06c93a3a635e2b8` · J647 `9e7c4224896cd9257d102bef728073db0f142269358b42c244ae4e1ec9ac1f82` · J644 `118540ea2cf3f7b3b26979150e44edc54ee3f87cb79da296ca7df21fce70c717` · J637 `03339547317e8d543f65696ac0e6af412778f6bbb62bbdc2ad31cae96c442648` · J585 `da5e495910a6b6f669389bdfd7184960949a62b469d6bbd78f78384e5364b0c0` · J503 `f567e9f6dc606c6a9eceff8dc54ed798c2645536ea47c2e8da42a8bc3867a76e` · J502 `395385929be5b706a079286738f6e47cf73f7694d990ca6fe02c2696d72a7f6c` · J425 pre-migration gameplay `5a25bb9fe001440a01316bbe79f4e8269ac37e6bf33e91d4c20e91f1f9ae63b0` · J323 paused Moon `893b03c4162a79d4cc9b194fb07b412695e34c1b50439434230902289bd385a9` |
| Retained old input | Steam 21587608 and Unity 2021.3.33f1 under `work/migrations/steam-21587608` (old rollbacks only) |

Retention rules for these rollbacks: [docs/history-retention.md](docs/history-retention.md).

## What runs today

Unless marked otherwise, these were observed on the test device with diagnostic assists
(invincibility, and sometimes high damage or fast charge). They show the systems run;
they are not normal-difficulty acceptance.

- **Catalogs:** the measured original content catalogs register natively on device (295 items,
  59 equipment, 290 bodies, 204 masters, 563 skills, 76 scenes; zero errors).
  J1022 retains native network-sound mapping and fresh original audio-camera
  context on Lakes/Goolake, with all three original highlight prefabs ready and
  no unexplained errors in the passing standard-control logs. Natural release
  and original highlight appearance remain unqualified.
- **Menu → run:** recovered offline menu with original difficulty choice, the 20-entry
  survivor roster (profile-eligible ones enabled) and earned loadout choices, then
  original world play.
- **Survivors:** Commando and Huntress by ordinary selection; Bandit2, Toolbot, Engi and
  Loader through developer-only selection (J504). Four canonical native callbacks
  passed for Commando, Huntress and Bandit2 (J603), Toolbot including utility
  (J611), Mage (J614), Mercenary (J618) and Engineer (J621). Engineer's corrected
  setup and native mines/shields/turrets pass (J631), with player projectile and owned-summon
  damage observed in J645. The full alternate kit records native Walker-owned damage in J705. Three Engineer alternate callbacks plus UI-abandon/restart pass (J653); the full alternate loadout also cleans up and restarts on e09920fd… (J686). Mage's four alternate callbacks and native UI-abandon/restart pass (J673/J674); isolated alternate utility input passes J699 and native Earth Shard projectile occurrence passes J708; damage/full effects remain open. Huntress's four alternates pass bounded callbacks/output (J684); Bandit2's three alternates pass with a player-owned shiv hit (J692), with full ability semantics open. The repaired full kit reaches 60 s with all four callbacks on e09920fd… (J685), but no stakes are observed in that case; J667 intermittence, Laser Cutter damage/sequence and complete ability semantics remain open.
  REX defaults and live alternate inventory pass (J623/J706); three alternates record native callbacks, projectiles and owned-summon damage (J711), with complete semantics open. Loader passes a finite replay (J634), while intermittent
  LightningStake corruption remains unresolved. J1019 observes a clean bounded
  Loader window with three native slot callbacks. J1021 adds the existing
  four-slot input mode and observes all four callbacks plus original Hook/Pylon
  projectiles; complete ability semantics, natural teardown and the separate
  blue-elite defect remain open. Acrid and Captain pass (J625); Captain's bounded native supply-beacon deployment and ordinary return pass on 1311f105 in J784, with healing/full semantics open; fresh Acrid/Mercenary defaults and native alternate inventories pass on d545d800 (J715). Acrid alternates record Breath projectile/aggregate Blight occurrence (J718), with impact/ticks incomplete. Mercenary alternates and source UI-abandon/restart pass on 12d79359 (J737), with Evis projectile occurrence and no rejected lookup; mapped Evis damage is earlier f054 evidence (J733), while full semantics remain open. Fresh MUL-T/Commando defaults and exact native alternate identities pass on b32998b8 (J727); bounded alternate callbacks/live inventories pass on f0546585 (J735), with Buzzsaw activation and grenade damage still open. J790 passes the bounded native Dual Wield/Buzzsaw offhand activation after repairing early equipment availability; damage and full semantics remain open. J797 records the strict primary observer's CLR-null operand. J801 verifies Commando-only scoping on the new player; the separate stock MUL-T retry then fails in the shared combat observer, with strict teardown refusal retained. J814 passes a fresh stock MUL-T four-callback retry on 91b0b7c9… without reproducing that NRE; its cause, full kit semantics and MUL-T teardown remain open.
- **Stages:** Huntress completed four original boss/charge/exit transitions
  Lakes → Goolake → Wisp Graveyard → Ship Graveyard → Sky Meadow (J504). 23 destinations
  are staged; nine DLC scenes are staged but unplayed pending a truthful expansion-availability
  path. The Gold Shores portal/mission path runs (J485). J785's native Siren
  retry identifies a temporary-Stage handoff contradiction before registration;
  its correction is in J788's default-verified player. J792 diagnoses the later ID-2 refusal as premature owned Director activation; its strict handoff correction is in the J793 default-verified player. J795 accepts bounded native Siren source entry, exact 12-egg Listening registration and cleanup. J812 reaches that registration with an active native Huntress tracker, then times out with no selected-egg target match or encounter start; source teardown is unobserved at that stop. J822 admits the corrected host timing and captures two native eligibility snapshots: the selected visible egg is beyond Huntress's 60 m tracking range, with repeated approach recovery and no selected-egg tracker match. J844 reaches Ship Graveyard after three exits on 8357db8b… but the recorder captures no samples: its additional stall gate is not met in the final report despite the egg remaining out of range. J933 preserves initial exact admission and later live-ID subsets on stock Commando, then times out without native boss identity; the last selected egg is occluded and no navigation samples are captured. J943 joins the preserved native twelve-slot list to two Unity-null slots, ten known-live slots and counter two/threshold six; it times out without encounter start or causal damage evidence. Egg interaction and the boss mission remain open.
- **World:** original director decks and placement, purchases (chests, Turret1, Drone1),
  items, equipment, procs, elites, death → results. Native completed-session cleanup, Engineer shield-lease release and a healthy
  same-process restart pass on f57e172b… with three alternate skills and explicit observer
  lifecycle checks (J653); earlier loss-only proof is J609. The separate native first-stage UI-abandon/restart path passes on 885ea294… with a returned shrine loan and healthy observer lifecycle (J730); native transport remains open.
- **Progression:** Android-only native profile, results and settings; original achievement
  classes evaluate at genuine events, and assisted runs are excluded from permanent awards
  (profile holds 13 applied runs).
- **Performance:** 120 Hz display with a 300 FPS request; first stage about 116 FPS under a
  firing workload; crowded later stages fall below 60 FPS with the main thread over budget.
  Hardware profiling refuses (J610), as does app profiling on adopted storage
  (J636). J761 obtains a 15 s app-scope trace on internal test device in Ship Graveyard;
  enumeration dominates the native call tree, with managed attribution open.

Per-subsystem detail and vocabulary (original / recovered / adapted / approximate /
unavailable): [docs/subsystem-coverage.md](docs/subsystem-coverage.md).

## Open

- An unassisted full run and normal-difficulty combat acceptance.
- Moon, finale and escape: deferred; manual only, never navigated autonomously.
- Stock Steam startup, cloud profiles, platform identity: unavailable by design (no
  fabricated ownership or service success).
- Audio integration has bounded device evidence; playback remains unqualified.
  J941 verifies media delivery and nonzero PCM in bounded first-stage windows
  on the exact owned music output.
  J959 verifies a persisted, truncated original-output waveform after Term/disarm
  by separate read-only salvage and finds strong music-media similarity. Its automatic
  route remains failed; J962 independently verifies cold-readback persistence.
  Event attribution remains open.
  Continuous destination-stage output, wider effects,
  spatial behavior, speaker audibility and composed natural Term/restart remain
  open. J845 separately measures one original pickup in an isolated managed
  player; J627/J640 retain clip-fallback limits.
- Licensed Rewired and generic physical controllers remain open.
- Complete skill kits, most positive ordinary unlock grants, DLC scene play.
- Native first-stage loss/restart passes on J752's APK in J753, including genuine
  defeat, strict cleanup and a healthy same-process second session. J798's current
  native Normal attempt remains live without error at its 900 s host deadline;
  no defeat or restart is accepted. Native stage transport, repeated long sessions
  and ordinary difficulty remain open.
- J887 observes native Huntress selected-skin readiness but source-camera
  activation and end-run failures; repair graphics fidelity and camera-state
  lifecycle before promoting the opt-in route. J915 observes skin/listener teardown
  on 6435f1ff, absent camera delegate/zero pumps and an actual next-menu free-choice
  refusal. J917 verifies the binding retry and camera context, but records severe visual
  artifacts. J919 repeats those artifacts but observes clean owned teardown and
  genuine next-menu return on the player containing J914's dependency repair.
  Two obsolete historical host predicates refuse the raw selected route; preserve
  that result. J935 now includes the bounded render and source-camera observers;
  J936 observes matching callback/tracker identity but disabled/null-material
  renderers. J942 confirms a known-null source material cache and dirty state
  in a matched callback, while its separate survival/menu route fails. J947 verifies
  the original cache prerequisite and bounded model teardown/menu return; verify the now-rooted RampFog candidate and remaining material fidelity. Healthy second-run play, broader
  survivors/skins and visual parity remain open.
- PC visual parity, sustained 60 FPS and thermals, managed-memory growth across
  sessions. J773 releases completed session references. J775 and J787 prune
  destroyed entries from original static registries (depossession, item display
  rules, drop tables, the never-drained team indicator queue); managed growth
  falls only from ~57 to ~52 MB per session on the spare test device, and the rest is not
  reachable from enumerable roots. Menu PSS is not monotonic over five sessions.
  Native indicator lifecycle is enabled in J804/J805; actual rendering and
  native teardown remain unaccepted.

Work ownership: this gameplay session continues original gameplay, audio and
animations on the adopted-storage test device only. The separate public-alpha session
owns launcher/packaging, controls/touch/rebinding, settings/UI, end-run menus,
feedback, stability/memory growth and playtest tooling on internal test device. The spare test device
requires explicit agreement before further use. Shared Unity builds retain the
host mutex; main is synchronized with a fast-forward-only rebase pull before
each push.

## Next actions

1. Fresh-editor code-only builds no longer depend on an earlier bundle build for their
   linker roots (J506); run `./dev check-baseline` after each rebuild
   ([docs/BASELINE.md](docs/BASELINE.md)).
2. Continue broad survivor and special-realm gameplay integration (J504 direction).
   60 FPS is the release target, not a gate for each batch; investigate large
   unexplained regressions only.
3. Keep J503, J502, J425 and J323 executable; sleep the OLED whenever idle.
4. Structural cleanup: Phases 0, 1 and 3–5 of the cleanup plan are done. Phase 2: the runtime
   config and content recipe are generated from public recipes (J551); all 222 adapted assets,
   40 of 229 additions and the three transformed assemblies are reproducible (J552–J563); the 189
   inherited files are in a hash-verified local store (J564). The from-scratch rebuild reproduces
   86,811 of 91,841 files byte-identically on the host, including all 352 shader outputs,
   and 190 of the 204 inherited-store files are regenerated; its binding gate passes
   (J567–J575); since J738 builds stage only committed sources, and from a clean checkout of
   the accepted `069eab7` all twelve host steps reproduce 87,184 files with no pinned catalog
   input (J750); R9 on that destination passed both device checks first time (J751), and with the
   working project's BlueNoise importer restored to its export form R9 reports `equal: true` (J752). R9 builds the destination from a fresh Library into an APK that passes
   both device checks (J582; rerun J586, both checks passing first time). With the Timeline pin
   (J584) and the layered reimport (J585), R9 logs no new reimport error, and its APK matches the
   baseline except `Hidden/Compositing` (open), the path-dependent Burst library and build metadata.
   One gate file still differs: `BlueNoise_R8_1.png.meta`, working-project drift (J592). Since J597 the
   rebuild reads no migration evidence (R2 selects from public recipes; R5 and R7 regenerate their
   inputs; every step still byte-identical). Still needed for a rebuild from public inputs alone:
   14 files from the inherited store (11 editor-built HUD assets, FastDirector, `Strings.json`, the
   TMP mobile shader, so J558 is still open), 47 hash-pinned local analysis inputs (R2–R4's catalog analysis is regenerated on the host since J725) and the
   provenance map's role in selecting membership. The working project itself is still migrated. The remaining
   debt is in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#known-structural-debt).
