# Porting state — 2026-10-12 PDT

Architecture C remains active: original managed code, converted Android content and explicit platform adapters. The user approves Steam **25475991** with exact official ARM64 Unity **2021.3.45f2 / 88f88f591b2e** and its Android modules. Ownership/authentication/entitlement checks remain intact. A complete original offline game and visual parity remain unfinished.

## Current integration — J431/J432

Accepted input: `6af7ed94619fe1b4346974b4486afa03a8d1625a7820e92da0ff74d57208fe88`. Forty-nine runtime assemblies retain reviewed identities and nineteen optional boundaries; 47,375 other methods remain unchanged. The complete discovered closure has 42,292 files, plus 79 composed-only dependencies. All 6,515 typed host roots pass; quarantine is empty and unresolved reference findings remain explicit.

**Fresh Android catalog acceptance:** seven original providers and thirteen native catalog initializers finish on Nova in **98.526 seconds**, zero errors. Counts match host: 295 items, 59 equipment, 290 bodies, 204 masters, 275 buffs, 20 elites, 414 projectiles, 76 scenes, 1,897 configurations, 563 skills, 21 drones and 1,679 baked effects. This establishes native registration; the live game's complete pools/session lifecycle are not integrated yet. Evidence: `work/experiments/whole-catalog/latest.json` → `integration-latest.json` → `device-latest.json`.

The updated composed APK/payload builds and updates the same app on adopted storage (91 bundles, approximately 1.67 GiB). Recovered menu, Commando spawn and the first original director enemy now execute. Migration repairs preserve current scene contracts, original script execution orders and body-handling presets, early state registration, numeric configuration types, baked-effect indices and existing bundle ownership. The new SpawnBody catalog lookup now selects owned adapted actor templates. Original scene-policy initialization runs unchanged and no waiver is manufactured.

**Current exit: candidate33 composed Android integration passes.** Complete original item/equipment/buff families (295/59/275), thirteen native tiers and629 native static bindings now serve live gameplay. All84 original item-behavior associations are preserved and scheduled through the adapted inventory lifecycle. Fresh-profile requirements still permit42ordinary item drops/10equipment; no unlock, expansion or entitlement is granted. Native requirements replace the maintained loot list.

Candidate33 executes431.144world seconds,34kills and four genuine transitions through Sky Meadow, with full world/clock/behavior/provider/results cleanup and zero current-process errors. The earned Vagrant item runs original Recharge/Ready states with native host authority; a reversible local-session adapter resolves the preceding attachment authority error while retaining its source identity flag. Invincibility/high damage/fast charge ON; movement/jump OFF. No normal combat/holdout/full-run acceptance. 129 host tests and exact-editor compilation pass. Evidence: `work/experiments/input-migration/composed-25475991/verification/20261012T191557.390124Z`; APK `1b2544a0b090742fd6fb36349cb75de400f5e4fa318db2617bbcf7f99ef4d772`.

Detailed material/property census is opt-in; ordinary objective/error/cleanup evidence remains. Final report1.80MB; instrumented frame pacing85.469ms mean/5,212frames remains unresolved, not sustained performance acceptance. Visual review retains white item icons and incorrect character/rendering presentation; no parity claim.

## Rollback, device and storage

- Updated candidate31 remains the immediate integration rollback: APK `a27535f251fa7083e746c9e6f4f1aaada2095c797856d362d2411819458b55b4`; J431 evidence remains immutable.
- J425 integrated gameplay rollback: APK `5a25bb9fe001440a01316bbe79f4e8269ac37e6bf33e91d4c20e91f1f9ae63b0`, source/evidence `work/experiments/scene-runtime/20261008T163328.528634Z`.
- J323 paused Moon: APK `893b03c4162a79d4cc9b194fb07b412695e34c1b50439434230902289bd385a9`, source/evidence `work/experiments/scene-runtime/20261006T034153.546343Z`. Do not autonomously navigate Moon/finale.
- Old input Steam21587608 is hash-verified/read-only under `work/inputs/steam-21587608`; old33f1 editor and J428 project remain under `work/migrations/steam-21587608/lab-project`. J428 APK `50456ae5c0bb02fbf0fec699943ec61383566d8a300063d730f1d12cbed199ef` remains available during migration.
- Use only the configured adopted-storage Nova and `dev.ror2lab.arm64`, updating in place. Recheck live storage, package placement and runtime backing each install. No unrelated data/storage changes; do not control Thor. Sleep OLED whenever idle.
- Retain two accepted executable rollbacks plus active migration material; prune superseded generated outputs while preserving findings/receipts. Retired compressed sources are development history, not cache: `docs/history-retention.md`. Avoid new full snapshots.

## Next action and open boundaries

Keep candidate33 as the updated integrated base, with candidate31 recoverable. Next connect native body/master/skill/state catalogs to live spawning and session ownership. Honor original AddressablesLoadHelper.CanLoadType/JunkContent explicit-category policy: raw labels include23extra bodies/10masters/52skills/40families. The cheap host graph matches native290bodies/204masters/563skills/378families, with zero missing body/master scripts; three unassigned master bodies, one empty skill variant and ten unresolved state references require contextual review, not automatic quarantine. Local graph/diff records: `work/experiments/whole-catalog/gameplay/host-actor-*.json`. Use large independent batches and cheap host checks, then one composed Android test; skip manual/Moon/finale routing. Keep original PC images/binaries as visual authority and defer ambiguous visuals to a later PC differential pass.

Stock Steam-backed startup/profile, licensed audio/Rewired integration, complete content behavior, session retention, normal combat/death/full route, Moon/escape and sustained performance remain open. Existing Android-only results/settings are adapted. Reward/provider release now passes after pairing the new fifth team-effect lease. Broader session-memory growth remains open. AsyncManagement has moved to its own original assembly. Do not apply blind cache resets.

Use `./dev doctor`, `./dev preflight`, `./dev test`. Reusable catalog/migration commands and scope: `docs/whole-catalog-integration.md`; failures: `docs/PORTING_JOURNAL.md`. Consult pinned prior art before new game-specific mechanisms. Keep public commits authored and sanitized; Conventional Commits plus staged privacy/IP review are mandatory.
