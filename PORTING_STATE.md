# Porting state

Last updated 2026-10-24 UTC after **J1040/J1045/J1046 (Main device),
J1043/J1044 (host), J1063 (owner code) and J1065 (private owner APK device case)**.
R36 diagnostic bda30f33 passes both standard controls, strict current-process
log checks and independent installed-byte/profile/placement readback. The
source-camera route now reaches its bounded Outline observation without the
previous Bloom or Blit pass errors, with more visible color/background detail.
Rendering remains washed out and PC parity is open. Existing music-output
capture remains finite/nonzero; full audio and the failed warm Quit remain open.
J1045/J1046 also pass native first-stage UI-abandon and actual defeat/restart
on R36, retaining strict source retirement and effect-loan guards with original
audio ready. Main is stopped/asleep with the exact unchanged 13-run profile.
J1043's
skill-timed MainOutput capture and J1044's source-camera Uber composite batch
are host-qualified, default off and queued for one full build after the shared
editor handback. Accepted rollback stays J850 f1550ce0.
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
| Owner-build research | [J1063](docs/PORTING_JOURNAL.md#j1063--complete-the-source-input-host-native-owner-build) completes public original-input host game-code production. [J1065](docs/PORTING_JOURNAL.md#j1065--qualify-private-owner-apk-preparation-upgrade-and-unity-lifecycle) qualifies private owner-APK preparation, upgrade retention, Unity lifecycle and assisted controls. Independent protected-output production, licensed native input, Burst/content/shaders, full-player Android tools, on-device signing/installer UX and matched performance remain open. Architecture C and desktop fallback stay fixed. |
| Latest device-verified APK | J1040/R36 diagnostic `bda30f33a62d62176cd45fd9cc0bd50ed5fe4e12d325ddc7ef19e948ec0fd3e7`, source 1428fdf: full content/player build, both strict standard controls and independent terminal readback. The bounded source-view route no longer records the previous pass errors, while washed-out rendering remains. Existing selected-music-output PCM stays finite/nonzero. Full audio, natural Quit and visual acceptance remain open. Accepted J850 stays `f1550ce0ff030ea0fa7a1ab66de19d54ee7894a7ae2f5b344f993157d6713949`, source 1780ea9. |
| Installed now | Main has J1040/R36 bda30f33 in adopted storage. J1046 independently rehashes its installed bytes and unchanged profile after native source-stage defeat/restart, with selector/process absent and display asleep. The owner-build device is recorded separately below. |
| Owner candidate installed now | J1065 version 2 `4960fba8ed5e727639c4f156e2f08cf92a6b6486790bb0ab295925e9bd212de0`, producer source b9d74dd7, is independently rehashed in internal storage on the assigned owner device. Its J850 code/content, both controls, ordinary menu/warm re-entry and exact zero-run profile/settings retention pass; process/selector absent and physical panel off. This private candidate has no R36 audio integration and is not a public phone converter. |
| Runtime source since verified APK | J1043/8497bda adds default-off MainOutput capture timing through the authoritative skill observer. J1044/c712bf5 restores the exact source-camera Uber composite contract through an independently selected generator and catalog replay. Host contracts, pins and clean-clone CI pass; neither change is in R36. Both selectors remain inactive pending the shared editor handback and one full content/player build. The active audio selection still requests the existing MusicController output. |
| Previous diagnostic rollback | J1034/R35 `47d14cb855ce8fefdf2406d55591d13165665c4a160ab7d71f435c6469faba6e`, source 919e72a, retains both controls and J1037's saved nonzero music prefix/failed warm Quit. Older diagnostic APKs (R26–R34) were discarded as rebuildable outputs in J1051; their hashes and source commits stay in the journal. |
| Device tooling | J755 verifies discovery, allowlist/profiles, separate ownership/runtime receipts, fresh reserves and idle screens on all three. The secondary test device passes both checks and produces J761's app-scope trace. The spare test device passes J762's automatic game checks and isolated audio; generic physical input remains unverified. Unity builds serialize while selected-device runs overlap. J888 verifies checked observations and teardown in both alpha standard modes. |
| Executable rollbacks | Accepted J850 `f1550ce0ff030ea0fa7a1ab66de19d54ee7894a7ae2f5b344f993157d6713949` · J425 pre-migration gameplay `5a25bb9fe001440a01316bbe79f4e8269ac37e6bf33e91d4c20e91f1f9ae63b0` · J323 paused Moon `893b03c4162a79d4cc9b194fb07b412695e34c1b50439434230902289bd385a9`. J1051 discarded the older J502–J840 executables as rebuildable outputs (rebuild from the journal's source commit). Only APKs named on this page, in `docs/BASELINE.md`, in device receipts or in the coordination lock are retained by `scripts/prune-generated.py`. |
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
  J1037 verifies a nonzero MusicController-output prefix after both Term returns
  and disarm on R35, while warm Quit produces a focus-loss ANR. Event attribution
  remains open. Continuous destination-stage output, wider effects,
  spatial behavior, speaker audibility and composed natural Term/restart remain
  open. J845 separately measures one original pickup in an isolated managed
  player; J627/J640 retain clip-fallback limits.
- Licensed Rewired and generic physical controllers remain open.
- Complete skill kits, most positive ordinary unlock grants, DLC scene play.
- J1045 revalidates native first-stage UI-abandon, strict source-owner cleanup,
  effect-loan return and healthy same-process restart on R36. A chance-shrine
  success co-occurs with a player Armor Plate pickup; natural boss/teleporter
  reward and exit remain unobserved. No full stage-clear acceptance follows.
- J1046 passes native Normal defeat/restart on R36 with original audio ready:
  one original Commando DeathState, corpse/ragdoll/effect witnesses, strict
  cleanup and healthy same-process second play. It remains assisted, not
  ordinary-difficulty acceptance. Native stage transport, repeated long sessions
  and unassisted combat remain open.
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
  survivors/skins and visual parity remain open. J1040 retains the supported
  two-pass Outline observation and removes the
  previous Bloom and unnamed Blit errors from the bounded source-view window.
  The image has more visible color/background detail but remains washed out;
  full shader/material/fog fidelity and original-PC parity remain open.
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
