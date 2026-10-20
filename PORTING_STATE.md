# Porting state

Last updated 2026-10-20 after **J788** (both default controls pass; targeted MUL-T exposes an earlier native spawn prerequisite).
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
| Latest device-verified APK | `be26c21c4cd8ff15a8a663528216cf7a69394a51d8b9441a63a1a496f83e98b5` — J788 shared code-only build from committed source 067cab3; both default checks pass; 106 runtime sources, 251 frozen inputs and 266 unchanged payload hashes; exact debugging symbols retained. Targeted MUL-T fails before world play. |
| Installed now | be26c21c… on both Novas, under adopted-only and internal-reserve policies respectively. Thor has 2679a11a… on the parallel memory track, with separate acceptance. Root default controls qualify adopted Nova; internal Nova records the failed MUL-T trial. Isolated audio removes its owned fixtures after each trial. Idle displays sleep. |
| Runtime source since verified APK | Accepted be26c21c… binds 067cab3fea15f0c2bf18f038346b8b17ab276531, including J785’s source-enabled machine restoration and temporary-Stage handoff order plus the earlier Captain, Siren, terminal-observation and root-attribution work. J787’s later static-registry retirement source (21db949) and 0abae2e are outside this APK; parallel checks remain separate. J788’s MUL-T exception requires another owner-order investigation; native Siren entry remains unaccepted. The Android Wwise support generator is reproducible, but the isolated render-owner remains outside the game and audio is unavailable. |
| Device tooling | J755 verifies discovery, allowlist/profiles, separate ownership/runtime receipts, fresh reserves and idle screens on all three. Second Nova passes both checks and produces J761's app-scope trace. Thor passes J762's automatic game checks and isolated audio; generic physical input remains unverified. Unity builds serialize while selected-device runs overlap. |
| Executable rollbacks | J783 `1311f1057275ef2a34a3fc964a6f79e033086243d066deea40775b9178d2bba5` · J776 `bbd1f3c15958ee42d272d58770a8caa2a73e327354bc668d9564bbd595656eb9` · J771 `0dd3f57328883d9dd927362775277b876cbf59ddaa17e0a9d0e719a15094684d` (exact debugging symbols retained) · J767 `2aa936c059331c6a2dcf2a3ef56ef928103707b1f009532dbfaa1c6f6c9697c3` · J764 `d7974718a48c008d83ab0bb411a8ea22093cbc23950a76e7cfffa17297285bfa` · J762 `96006814dd2ba80f65cd24413c50c11c3061060f9d90977296f1e00d71ec7fd1` · J758 `aabf41ab5ece8a34d9ac4b70946dad5d8b827baa40e4dd927afd98e6ff15deee` · J752 `aa732f88948062c43a59378bf7dd53f1a473c828a479adbaee32e976207fb159` · J749 `771fc75282b45197d0dd25d3d537a121112ca35830c8d4dd516711aa7aa813cf` · J745 `caeeb62fe45e7b8bad8a89272390a11a392152b975277660675a75e56a230453` · J737 `12d793593d216ea50d6db400fb4e8f7a3258657acd39a382181f0dc6b18035f8` · J728 `885ea2946869ca8a206739cf74acd9bbf75705651d5f3974c30a56724d93e715` · J724 `b32998b87706977e2945ae3b709e26486b76bf9403894262877a9e3829d80b54` · J707 `d545d80048fbc26b882ada5ecb1e38346239f121d8cdb00266ef3d29be703bee` · J702 `efb0ba9354923c1fbe453d28364018e078627cd15c65fc4813dcc3f0c13d577d` · J698 `fe4dc0de0f70ec70b699e9d54e55e3e657c0a89f1f9efb52ee58411ed0bcc383` · J695 `039bc73d59822801da9258a7f90b5bfa7e77080e0c4d49058f81916a61f0cfbc` · J689 `55dee31826b7ecd545488d601490ba92623d6640a711e9a534fdd2c898ede861` · J680 `e09920fd9df2c5b03416b33766fbdaf4c64f2feeeee9b68eff200435c0716ebc` · J670 `ad84d0cb55bc6a18dabf67e90839c78100abcb846c6feaff13c758a6b8a6fb69` · J663 `6506b99bfa5004960721868b222d15010718a81f4c55f28bd29d153976d97cec` · J657 `86d2542aadcc12dbfdb53fe957d7aedf32ebeb8d38c94fbf4732ef5211ed7d03` · J654 `f57e172b9da1a5717144355266cd2e1a1de93fa775c14233a06c93a3a635e2b8` · J647 `9e7c4224896cd9257d102bef728073db0f142269358b42c244ae4e1ec9ac1f82` · J644 `118540ea2cf3f7b3b26979150e44edc54ee3f87cb79da296ca7df21fce70c717` · J637 `03339547317e8d543f65696ac0e6af412778f6bbb62bbdc2ad31cae96c442648` · J585 `da5e495910a6b6f669389bdfd7184960949a62b469d6bbd78f78384e5364b0c0` · J503 `f567e9f6dc606c6a9eceff8dc54ed798c2645536ea47c2e8da42a8bc3867a76e` · J502 `395385929be5b706a079286738f6e47cf73f7694d990ca6fe02c2696d72a7f6c` · J425 pre-migration gameplay `5a25bb9fe001440a01316bbe79f4e8269ac37e6bf33e91d4c20e91f1f9ae63b0` · J323 paused Moon `893b03c4162a79d4cc9b194fb07b412695e34c1b50439434230902289bd385a9` |
| Retained old input | Steam 21587608 and Unity 2021.3.33f1 under `work/migrations/steam-21587608` (old rollbacks only) |

Retention rules for these rollbacks: [docs/history-retention.md](docs/history-retention.md).

## What runs today

Unless marked otherwise, these were observed on the Nova with diagnostic assists
(invincibility, and sometimes high damage or fast charge). They show the systems run;
they are not normal-difficulty acceptance.

- **Catalogs:** all original content catalogs register natively on device (295 items,
  59 equipment, 290 bodies, 204 masters, 563 skills, 76 scenes; zero errors).
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
  LightningStake corruption remains unresolved. Acrid and Captain pass (J625); Captain's bounded native supply-beacon deployment and ordinary return pass on 1311f105 in J784, with healing/full semantics open; fresh Acrid/Mercenary defaults and native alternate inventories pass on d545d800 (J715). Acrid alternates record Breath projectile/aggregate Blight occurrence (J718), with impact/ticks incomplete. Mercenary alternates and source UI-abandon/restart pass on 12d79359 (J737), with Evis projectile occurrence and no rejected lookup; mapped Evis damage is earlier f054 evidence (J733), while full semantics remain open. Fresh MUL-T/Commando defaults and exact native alternate identities pass on b32998b8 (J727); bounded alternate callbacks/live inventories pass on f0546585 (J735), with Buzzsaw activation and grenade damage still open. J784 records persistent disabled/uninitialized Weapon2 at the native offhand deadline; J788’s corrected scheduling exposes an earlier native equipment-expansion exception during spawn. No Buzzsaw acceptance follows.
- **Stages:** Huntress completed four original boss/charge/exit transitions
  Lakes → Goolake → Wisp Graveyard → Ship Graveyard → Sky Meadow (J504). 23 destinations
  are staged; nine DLC scenes are staged but unplayed pending a truthful expansion-availability
  path. The Gold Shores portal/mission path runs (J485). J785's native Siren
  retry identifies a temporary-Stage handoff contradiction before registration;
  its correction is in J788's default-verified player, with native entry still unaccepted.
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
  (J636). J761 obtains a 15 s app-scope trace on internal Nova in Ship Graveyard;
  enumeration dominates the native call tree, with managed attribution open.

Per-subsystem detail and vocabulary (original / recovered / adapted / approximate /
unavailable): [docs/subsystem-coverage.md](docs/subsystem-coverage.md).

## Open

- An unassisted full run and normal-difficulty combat acceptance.
- Moon, finale and escape: deferred; manual only, never navigated autonomously.
- Stock Steam startup, cloud profiles, platform identity: unavailable by design (no
  fabricated ownership or service success).
- Audio remains unavailable: J722 identifies the accepted native wrapper as Wwise
  2023.1.8.8601 and records the Vorbis/seven-effect requirements. An authorized
  Android SDK and matching Unity Integration are supplied locally. J732 proves
  independent native PCM output and unchanged original Init load/unload. J734
  posts an unchanged original Global event and captures nonzero PCM, but strict
  validation fails on the unavailable Controller Speaker output plugin. An
  explicit Android bus adaptation succeeds but still fails an Init-time plugin
  lookup under cumulative error observation (J736). A fixture-only Init output
  metadata adaptation then loads/unloads with zero post-Term cumulative errors
  (J740), then supports one unchanged Global UI event with EndOfEvent, finite
  nonzero PCM and zero post-Term cumulative errors (J742). The retained managed
  ABI, wider bank behavior and game lifecycle remain open. J743 maps the official
  library in a fresh Unity player. J747 localizes the managed fixture refusal
  to import-metadata validation before the native initialized query; its verbose
  log report is also truncated and rejected. J744 publicly reproduces the tested Init variant; other private fixture
  producers remain unwired.
  J756's revised managed fixture initializes Wwise on Thor but refuses Init
  filename loading. J759 registers the persistent POSIX path with AddBasePath,
  then loads/unloads the unchanged Init and cleans up. Its current-process log
  still records five middleware errors for the Windows output plugin/device;
  no event, PCM, cumulative-error or composed-audio acceptance follows.
  J778's corrected standalone managed player passes the numeric native monitor
  control and strict teardown. That player uses the wrong message encoding; J781 reproduces the host
  correction. J786 passes readable monitoring and native per-frame rendering, then
  completes one original Global event with EndOfEvent and zero post-Init monitored
  errors. Its strict capture check refuses unfinished RIFF evidence and lacks
  WAVE_FORMAT_EXTENSIBLE support; PCM and audibility remain unvalidated. These are isolated fixtures, and no
  composed-audio gate is accepted. J770 makes the incomplete ABI candidate
  reproducible without enabling audio. Wider bank behavior and production
  lifecycle remain open.
  J627 rejects a proposed static UI fallback; J640 resolves its numeric default
  but leaves native switch/routing semantics unproven.
  Licensed Rewired and generic controllers remain open.
- Complete skill kits, most positive ordinary unlock grants, DLC scene play.
- Native first-stage loss/restart passes on J752's APK in J753, including genuine
  defeat, strict cleanup and a healthy same-process second session. Native stage
  transport, repeated long sessions and ordinary difficulty remain open.
- PC visual parity, sustained 60 FPS and thermals, managed-memory growth across
  sessions. J773 releases completed session references. J775 and J787 prune
  destroyed entries from original static registries (depossession, item display
  rules, drop tables, the never-drained team indicator queue); managed growth
  falls only from ~57 to ~52 MB per session on Thor, and the rest is not
  reachable from enumerable roots. Menu PSS is not monotonic over five sessions.
  Original position indicators are unavailable: the port does not run
  `TeamComponent.Init`.

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
