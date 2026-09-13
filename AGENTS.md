# Porting laboratory handoff

Read `PORTING_STATE.md` first, then `environment/ENVIRONMENT_REPORT.md` and the relevant ADRs. Run `./dev doctor`. Read `docs/PORTING_JOURNAL.md` before repeating a failed experiment. This is a laboratory, not a working game port. Agent #3 should use the evidence to prepare a plan; do not infer game readiness from G2.

## Non-negotiable boundaries

- Never modify the original legitimate game installation. Configure its external path in ignored `work/config/local.json` (example in environment/).
- Never commit original game assets, binaries, decompiled source, generated Unity data, Wwise banks, proprietary middleware, account data, credentials or signing keys. All game-derived material stays under ignored `work/`. Raw logs/screenshots are local and may contain private data.
- Open tooling + transformations + user-supplied legitimate game input is the distribution model. Do not bypass DRM, ownership, entitlement, authentication or license checks. Optional offline service adapters must not claim ownership/authentication success.
- Exact editor: Unity **2021.3.33f1 (ee5a2aa03ab2), macOS ARM64**. Use bundled SDK/NDK/OpenJDK through scripts/env.sh. Canonical ADB is `/opt/homebrew/bin/adb`.
- Require the explicitly configured authorized device serial. Query current adopted storage and free space every install. Physical internal storage is nearly full. Never format, repartition, erase, change storage configuration, or remove/move existing games/data to make space.
- Never hardcode a portable SD path or remembered adopted UUID. Record package placement and runtime data backing after installation. The disposable lab package is `dev.ror2lab.arm64`; reset requires its local ownership receipt. Bootstrap smoke uses a separate package and refuses pre-existing installs.

## Scientific workflow

Observe → state a hypothesis → smallest meaningful change → `./dev preflight` → build → install/sync → run → collect logs/crash/screenshot → classify first failure → update state/journal → commit a logical checkpoint.

Use `./dev` as the obvious interface; see README for supported commands. Use the pinned Unity MCP for editor state/actions and deterministic CLIs for filesystem, Git/GitHub, device operations and editor/server startup. Never send concurrent editor mutations to the same Unity instance. Check an outstanding build completes before loading scenes or entering Play Mode. If compilation prevents MCP connection, repair the recorded first error and restart the isolated editor; do not treat mere tool presence as a passing test.

Run preflight before expensive builds. Input drift requires inventory/diff review and explicit local acceptance; do not silently apply patches to unknown builds. Preserve failed run directories and known-good APK/hash receipts. Do not clear all caches for a small code/shader change. Inspect the current first failure before extending scope.

Keep offline single-player first unless evidence requires otherwise. Retain local networking/authority semantics; online services are a separate gate. Prefer clean temporary adapters with explicit unavailable capabilities over giant gameplay rewrites. Preserve type/serialization identity when experimenting with precompiled assemblies. IL2CPP still AOT-compiles those assemblies.

The real device is the final authority. Never declare success from compilation, a loaded bundle container, or an editor screenshot alone. Runtime diagnostics are instrumented only in the lab harness; actual RoR2 run/audio/network state remains to be integrated.

After meaningful progress update concise PORTING_STATE.md, append failed experiments with evidence/revisit conditions to docs/PORTING_JOURNAL.md, and maintain milestones/backlog. Commit small logical changes after checking staged files for proprietary material. Avoid unrelated rewrites. Read ADR-001 before changing architecture.


## Prior-art-first rule

Before implementing a new RoR2-specific reconstruction, Addressables/content loader, serialization repair, gameplay observer, platform adapter, shader mechanism, middleware workaround or runtime diagnostic: identify the subsystem, consult `docs/community-prior-art.md`, inspect the relevant pinned community source, and cite its API knowledge, workaround, failure/version clue or observation technique in the experiment notes. Implement new machinery only for requirements still unsolved on Android. Current legitimate input and device evidence outrank community assumptions. This rule does not require ecosystem research for generic adb/Gradle/shell problems. Keep passed Rewired/Burst/L3/L4 results and package pins unless a concrete new contract or regression justifies revisiting them. Use Conventional Commit messages.

## Public-repository privacy gate

Before committing, run `python3 scripts/audit-public.py` against staged content. Raw bootstrap evidence stays ignored locally, as do all game-derived outputs. Publish authored summaries, never device/storage/display identifiers, private home paths, personal emails or authentication-session records. Use a GitHub noreply commit email. A passing pattern scan supplements manual IP/provenance and secret review; it does not replace them.
