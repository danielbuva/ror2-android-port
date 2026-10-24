# Porting laboratory handoff

Reading order: `PORTING_STATE.md` (current snapshot) → `docs/ARCHITECTURE.md` (pipeline, runtime, ownership) → the subsystem doc you need → search `docs/JOURNAL_INDEX.md` and read the matching `docs/PORTING_JOURNAL.md` entries before repeating any experiment. `environment/ENVIRONMENT_REPORT.md` and `docs/ADR-001-port-architecture.md` explain the toolchain and the chosen architecture. Run `./dev doctor`. This is a laboratory, not a finished port: never infer game readiness from a build, a host test or an assisted run.

## Non-negotiable boundaries

- Never modify the original legitimate game installation. Configure its external path in ignored `work/config/local.json` (example in environment/).
- Never commit original game assets, binaries, decompiled source, generated Unity data, Wwise banks, proprietary middleware, account data, credentials or signing keys. All game-derived material stays under ignored `work/`. The only image exceptions are the two repository-only promotional PNGs documented in [branding notes](docs/assets/branding/README.md) and the original launcher scene documented in [launcher provenance](launcher/PROVENANCE.md), pinned by exact path and SHA-256 in the public audit. This does not authorize other marketing art, game files or runtime redistribution. Raw logs/screenshots are local and may contain private data.
- Open tooling + transformations + user-supplied legitimate game input is the distribution model. Do not bypass DRM, ownership, entitlement, authentication or license checks. Optional offline service adapters must not claim ownership/authentication success.
- The lab must be reproducible from public source, the documented toolchain and the user's legitimate installation. Recipes (authored transformations, configuration, reproducible build steps) are tracked in `recipe/` after a provenance, privacy, licensing and sensitive-content audit recorded in `recipe/README.md`; generated game-derived content, private configuration and protected third-party material stay ignored. Recipes may name the minimum game asset paths, GUIDs, catalog names and relationships needed to reconstruct content locally; they must never reproduce protected content or substitute for owning the game.
- Exact editor: Unity **2021.3.45f2 (88f88f591b2e), macOS ARM64** (user-approved Steam migration; retain 2021.3.33f1 for old rollbacks). Use bundled SDK/NDK/OpenJDK through scripts/env.sh. Canonical ADB is `/opt/homebrew/bin/adb`.
- Require the explicitly configured authorized device serial. Query current adopted storage and free space every install. Physical internal storage is nearly full. Never format, repartition, erase, change storage configuration, or remove/move existing games/data to make space.
- Never hardcode a portable SD path or remembered adopted UUID. Record package placement and runtime data backing after installation. The disposable lab package is `dev.ror2lab.arm64`; reset requires its local ownership receipt. Bootstrap smoke uses a separate package and refuses pre-existing installs.

## Storage hygiene (mandatory)

The host disk is shared by every agent; unchecked build copies once filled
866 GB. Each agent cleans up after itself:

- When a build/run task finishes (pass or fail), and before ending a session,
  run `python3 scripts/prune-generated.py --apply`. It discards only rebuildable
  binaries (superseded build-cache entries, staged symbols, APK/AAB/symbol/
  libil2cpp/payload copies, Unity `Library`/`Bee`/`il2cppOutput` trees in
  experiment and coordination roots), keeps receipts/logs/evidence, protects
  every APK named in `PORTING_STATE.md`, `docs/BASELINE.md`, device receipts or
  `work/coordination/codex-runtime.lock`, and skips anything newer than 24 h.
- Never copy an APK, payload or Unity project into a run/review folder when a
  path plus SHA-256 reference works. Prefer APFS clones (`cp -c`) when a copy is
  unavoidable. Review checkouts and scratch Unity projects are deleted when the
  review ends.
- Pin an APK you still need by naming its hash in `PORTING_STATE.md` or the
  coordination lock; everything else is disposable after 24 h.
- Before starting a full build, check `df -h /System/Volumes/Data`; below 100 GB
  free, prune first and report if that does not restore it.
- Extra worktrees (`git worktree list`, `~/.codex/worktrees`) are removed when
  their PR merges or the task is abandoned.

## Scientific workflow

Observe → state a hypothesis → smallest meaningful change → `./dev preflight` → build → install/sync → run → collect logs/crash/screenshot → classify first failure → update state/journal → commit a logical checkpoint.

Use `./dev` as the obvious interface; see [docs/DEVELOPING.md](docs/DEVELOPING.md) for supported commands. Use the pinned Unity MCP for editor state/actions and deterministic CLIs for filesystem, Git/GitHub, device operations and editor/server startup. Never send concurrent editor mutations to the same Unity instance. Check an outstanding build completes before loading scenes or entering Play Mode. If compilation prevents MCP connection, repair the recorded first error and restart the isolated editor; do not treat mere tool presence as a passing test.

Whole-catalog builds (full, code-only and R9) refuse uncommitted or untracked changes under `tools/unity`, `tools/catalog` and `android/Assets/Editor`, and record the commit in the build receipt (`source.commit`, J738): commit before building (a WIP commit is fine), so the working project is always reproducible from Git. Python must pass CI's Ruff step: run `.local/lab-venv/bin/ruff format` and `ruff check` on the Python files you change before committing; the tracked pre-push hook (`scripts/git-hooks/pre-push`, enabled with `git config core.hooksPath scripts/git-hooks`) runs `scripts/ci-local.sh`, which repeats the GitHub host-tests check on the pushed commit in a fresh clone without `work/` or the Unity install, and refuses a push that would fail. Host tests that need the editor's Mono/Roslyn must `skipTest` when it is absent. Run preflight before expensive builds. Input drift requires inventory/diff review and explicit local acceptance; do not silently apply patches to unknown builds. Preserve failed run directories and known-good APK/hash receipts. Do not clear all caches for a small code/shader change. Inspect the current first failure before extending scope.

Keep offline single-player first unless evidence requires otherwise. Retain local networking/authority semantics; online services are a separate gate. Prefer clean temporary adapters with explicit unavailable capabilities over giant gameplay rewrites. Preserve type/serialization identity when experimenting with precompiled assemblies. IL2CPP still AOT-compiles those assemblies.

The real device is the final authority. Never declare success from compilation, a loaded bundle container, or an editor screenshot alone. Runtime diagnostics are instrumented only in the lab harness; actual RoR2 run/audio/network state remains to be integrated.

Commit small logical changes after checking staged files for proprietary material. Avoid unrelated rewrites. Read ADR-001 before changing architecture.

## Documentation rules

Each document has one job; record each result once and link to it elsewhere.

- `docs/PORTING_JOURNAL.md`: the only place an experiment's full result is written (hypothesis, change, evidence paths, APK hash, first failure, revisit conditions). Append a `## J<n> — <title>` entry, then run `python3 scripts/journal-index.py` to refresh `docs/JOURNAL_INDEX.md`.
- `PORTING_STATE.md`: a one-page snapshot. **Replace** its content after meaningful progress; never append history there. Keep "latest device-verified APK", "installed now" and "runtime source since that APK" as separate facts: Git history alone does not prove what is installed.
- `docs/execution-backlog.md`: open work only. `docs/milestones.md`: gate definitions and current status. `docs/risk-register.md`: risks with links to evidence. None of them copies journal reports.
- `docs/ARCHITECTURE.md`: update it when a file, owner or pipeline step is added, moved or retired.
- Superseded material moves to `docs/history/`; nothing labelled "current" lives there.
- Wrap prose at a readable width and put spaces between numbers and words.

## Definition of done

A feature is done when it has an understandable place in the current system, not only when its experiment passed:

1. Device evidence is recorded once in the journal and the index is regenerated; `PORTING_STATE.md` is replaced, not appended.
2. The behaviour lives in a named owner listed in `docs/ARCHITECTURE.md`, with its setup, teardown and state; shipped behaviour is not added as another case of the experiment switch in `MovementBatchProbe.RunSelectedProbe`.
3. Any new file under `work/` that the build reads has a generator in the repo, or is listed in `docs/LOCAL_STATE.md` as required local state with its reason. No new code reads a timestamped run folder directly.
4. A contract that can be checked off-device has a host test or an exact-editor fixture.
5. A new `./dev` action states in its help or in ARCHITECTURE whether it is current or historical.
6. No new build step edits authored source by exact-text replacement.

Historical storage follows the user's J427 cleanup authorization: of the older historical candidates, only J425 and the paused J323 Moon candidate remain ready-to-use rollbacks; the current executable rollbacks are listed in `PORTING_STATE.md`. Superseded source trees have adjacent `.retired.json` markers and hash-verified compressed content under ignored `work/retired-storage`; restore only a specifically needed tree using `scripts/compact-history.py`. Obsolete APK/payload outputs may require rebuilding. Preserve findings and receipts; do not treat the retired source store as disposable cache. See `docs/history-retention.md` before using an older checkpoint.


## Prior-art-first rule

Before implementing a new RoR2-specific reconstruction, Addressables/content loader, serialization repair, gameplay observer, platform adapter, shader mechanism, middleware workaround or runtime diagnostic: identify the subsystem, consult `docs/community-prior-art.md`, inspect the relevant pinned community source, and cite its API knowledge, workaround, failure/version clue or observation technique in the experiment notes. Implement new machinery only for requirements still unsolved on Android. Current legitimate input and device evidence outrank community assumptions. This rule does not require ecosystem research for generic adb/Gradle/shell problems. Keep passed Rewired/Burst/L3/L4 results and package pins unless a concrete new contract or regression justifies revisiting them. Use Conventional Commit messages.

## Public-repository privacy gate

Before committing, run `python3 scripts/audit-public.py` against staged content. Raw bootstrap evidence stays ignored locally, as do all game-derived outputs. Publish authored summaries, never device/storage/display identifiers, private home paths, personal emails or authentication-session records. Use a GitHub noreply commit email. Never mirror-push local app snapshot refs or private backup bundles. A passing pattern scan supplements manual IP/provenance and secret review; it does not replace them.
