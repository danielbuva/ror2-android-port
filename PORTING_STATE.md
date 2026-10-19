# Porting state

Last updated 2026-10-19 after **J682** (receipt-bound metadata host/editor gates; teardown repair pending).
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
| Latest device-verified APK | `e09920fd9df2c5b03416b33766fbdaf4c64f2feeeee9b68eff200435c0716ebc` — J678/J680 both default modes. Its opt-in native Stage/population/table readiness and actor events pass (J678); native teardown refuses on identity reset and retains recovery (J681). Mage alternates and default cleanup pass on prior ad84d0cb… (J673/J674), with complete semantics open. |
| Installed now | Accepted e09920fd… on current Nova adopted storage, installed in place and synced. Native UI-abandon failed safely before restart (J681); Huntress alternate case passed; Engineer's full alternate kit is active. Scoped receipts: `work/device/<serial>/`; original flat receipts retained. Huntress uses J676's exact inventory; its result is awaiting the journal entry. |
| Runtime source since verified APK | J682 metadata is integrated with 965 host tests, exact-editor path parity and 14-scene static parity; it is not built. Accepted e09920fd… contains 105 files with J669 actor events, J672 rolling observation and J675 source loot ownership. All 266 payload hashes match J665's full repaired content. J679 changes host-only selector identity; source-identity metadata is not built or device-verified. |
| Device tooling | J589/J595 host tests pass for selection, scoped receipts, path isolation, ambiguous bootstrap cleanup and the build mutex. Current Nova migration/install/both baseline modes pass. J679 binds diagnostic selector IDs to exact owned APK bytes, preserving earlier artifacts across project changes. Additional devices await user-supplied serials and live storage/display observations. |
| Executable rollbacks | J680 `e09920fd9df2c5b03416b33766fbdaf4c64f2feeeee9b68eff200435c0716ebc` · J670 `ad84d0cb55bc6a18dabf67e90839c78100abcb846c6feaff13c758a6b8a6fb69` · J663 `6506b99bfa5004960721868b222d15010718a81f4c55f28bd29d153976d97cec` · J657 `86d2542aadcc12dbfdb53fe957d7aedf32ebeb8d38c94fbf4732ef5211ed7d03` · J654 `f57e172b9da1a5717144355266cd2e1a1de93fa775c14233a06c93a3a635e2b8` · J647 `9e7c4224896cd9257d102bef728073db0f142269358b42c244ae4e1ec9ac1f82` · J644 `118540ea2cf3f7b3b26979150e44edc54ee3f87cb79da296ca7df21fce70c717` · J637 `03339547317e8d543f65696ac0e6af412778f6bbb62bbdc2ad31cae96c442648` · J585 `da5e495910a6b6f669389bdfd7184960949a62b469d6bbd78f78384e5364b0c0` · J503 `f567e9f6dc606c6a9eceff8dc54ed798c2645536ea47c2e8da42a8bc3867a76e` · J502 `395385929be5b706a079286738f6e47cf73f7694d990ca6fe02c2696d72a7f6c` · J425 pre-migration gameplay `5a25bb9fe001440a01316bbe79f4e8269ac37e6bf33e91d4c20e91f1f9ae63b0` · J323 paused Moon `893b03c4162a79d4cc9b194fb07b412695e34c1b50439434230902289bd385a9` |
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
  damage observed in J645. Three Engineer alternate callbacks plus UI-abandon/restart pass (J653). Mage's four alternate callbacks and native UI-abandon/restart pass (J673/J674), with Earth Shards output and full effects still open. The repaired full kit has all four callbacks before a known elite-stake error (J667); Laser Cutter damage/sequence and complete ability semantics remain open.
  REX passes (J623); Loader passes a finite replay (J634), while intermittent
  LightningStake corruption remains unresolved. Acrid and Captain pass (J625).
- **Stages:** Huntress completed four original boss/charge/exit transitions
  Lakes → Goolake → Wisp Graveyard → Ship Graveyard → Sky Meadow (J504). 23 destinations
  are staged; nine DLC scenes are staged but unplayed pending a truthful expansion-availability
  path. The Gold Shores portal/mission path runs (J485).
- **World:** original director decks and placement, purchases (chests, Turret1, Drone1),
  items, equipment, procs, elites, death → results. Native completed-session cleanup, Engineer shield-lease release and a healthy
  same-process restart pass on f57e172b… with three alternate skills and explicit observer
  lifecycle checks (J653); earlier loss-only proof is J609.
- **Progression:** Android-only native profile, results and settings; original achievement
  classes evaluate at genuine events, and assisted runs are excluded from permanent awards
  (profile holds 13 applied runs).
- **Performance:** 120 Hz display with a 300 FPS request; first stage about 116 FPS under a
  firing workload; crowded later stages fall below 60 FPS with the main thread over budget.
  Hardware profiling is permission-denied (J610); explicit software app profiling
  is separately refused by Android run-as on adopted storage (J636).

Per-subsystem detail and vocabulary (original / recovered / adapted / approximate /
unavailable): [docs/subsystem-coverage.md](docs/subsystem-coverage.md).

## Open

- An unassisted full run and normal-difficulty combat acceptance.
- Moon, finale and escape: deferred; manual only, never navigated autonomously.
- Stock Steam startup, cloud profiles, platform identity: unavailable by design (no
  fabricated ownership or service success).
- Audio remains unavailable: J591 narrows the candidate to Wwise 2023.1 with
  Vorbis and seven effects; an authorized Android runtime and bank compatibility
  remain unestablished. J627 rejects a proposed static UI fallback; J640 resolves its numeric default
  but leaves native switch/routing semantics unproven.
  Licensed Rewired and generic controllers remain open.
- Complete skill kits, most positive ordinary unlock grants, DLC scene play.
- PC visual parity, sustained 60 FPS and thermals, managed-memory growth across sessions.

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
   (J567–J575). R9 builds the destination from a fresh Library into an APK that passes
   both device checks (J582; rerun J586, both checks passing first time). With the Timeline pin
   (J584) and the layered reimport (J585), R9 logs no new reimport error, and its APK matches the
   baseline except `Hidden/Compositing` (open), the path-dependent Burst library and build metadata.
   One gate file still differs: `BlueNoise_R8_1.png.meta`, working-project drift (J592). Since J597 the
   rebuild reads no migration evidence (R2 selects from public recipes; R5 and R7 regenerate their
   inputs; every step still byte-identical). Still needed for a rebuild from public inputs alone:
   14 files from the inherited store (11 editor-built HUD assets, FastDirector, `Strings.json`, the
   TMP mobile shader, so J558 is still open), 57 hash-pinned local analysis inputs and the
   provenance map's role in selecting membership. The working project itself is still migrated. The remaining
   debt is in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#known-structural-debt).
